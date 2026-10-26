import json
import re
import urllib.parse
from typing import Dict, Any, List, Optional
from rapidfuzz import fuzz
from sqlmodel import Session, select

from app.config import settings, APPLICATIONS_DIR
from app.models import Application, Document, ExtractedField, Finding
from app.mock.router import get_aicte_record

def normalize_text_for_fuzzy(text: str) -> str:
    """Normalise text by removing spaces and punctuation before running rapidfuzz."""
    if not text:
        return ""
    return re.sub(r"[\s\W_]+", "", str(text)).lower()

def run_checklist_and_validity_checks(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField]
) -> List[Finding]:
    """
    (1) Required docs for category -> MISSING_DOC
    (2) Validity docs whose date < session_start -> EXPIRED_DOC
    """
    findings: List[Finding] = []
    checklist_cfg = settings.checklists or {}
    session_start = checklist_cfg.get("session_start", "2027-07-01")
    cat_cfg = checklist_cfg.get("categories", {}).get(app.category, {})
    required_docs = cat_cfg.get("required", [])

    present_doc_types = {d.doc_type for d in documents}
    doc_map = {d.doc_type: d for d in documents}

    # 1. Missing docs
    for req in required_docs:
        if req not in present_doc_types:
            evidence = {
                "items": [],
                "expected": f"Required document '{req}' present",
                "method": "checklist_validation",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": f"Document '{req}' is mandatory for category '{app.category}' but was not provided."
            }
            f = Finding(
                application_id=app.id,
                document_id=None,
                code="MISSING_DOC",
                severity="critical",
                title=f"Missing Document: {req}",
                message=f"Mandatory document '{req}' is missing for category '{app.category}'",
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            )
            findings.append(f)

    # 2. Validity checks (date < session_start)
    validity_cfg = checklist_cfg.get("validity", {})
    for doc_type, date_field in validity_cfg.items():
        doc_rec = doc_map.get(doc_type)
        if not doc_rec:
            continue

        # Find extracted field
        ef = next((f for f in fields if f.document_id == doc_rec.id and f.name == date_field), None)
        if ef and ef.value and ef.value not in ("null", "None"):
            val_date = str(ef.value).strip()
            if val_date < session_start:
                bbox = None
                if ef.bbox_json:
                    try:
                        bbox = json.loads(ef.bbox_json)
                    except Exception:
                        bbox = None

                evidence = {
                    "items": [{
                        "document_id": doc_rec.id,
                        "doc_type": doc_type,
                        "page": ef.page,
                        "bbox": bbox,
                        "field": date_field,
                        "value": val_date
                    }],
                    "expected": f"{date_field} >= {session_start}",
                    "method": "validity_date_check",
                    "related_applications": [],
                    "heatmap_url": None,
                    "explanation": f"{doc_type} expired on {val_date}; must be valid on session start {session_start}"
                }
                f = Finding(
                    application_id=app.id,
                    document_id=doc_rec.id,
                    code="EXPIRED_DOC",
                    severity="critical",
                    title=f"{doc_type} Expired before Session Start",
                    message=f"Document '{doc_type}' validity expired on {val_date}; must be valid on {session_start}",
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                    status="open"
                )
                findings.append(f)

    return findings

def run_cross_document_checks(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField]
) -> List[Finding]:
    """
    (3) Every cross_document group -> CROSS_DOC_MISMATCH with one evidence item per source
    """
    findings: List[Finding] = []
    consistency_cfg = settings.consistency or {}
    cross_doc_rules = consistency_cfg.get("cross_document", [])

    # Load application.json declared values
    app_folder = APPLICATIONS_DIR / app.folder
    app_data = {}
    if (app_folder / "application.json").exists():
        try:
            with open(app_folder / "application.json", "r", encoding="utf-8") as f:
                app_data = json.load(f)
        except Exception:
            app_data = {}

    doc_map = {d.doc_type: d for d in documents}
    field_map = {}
    for f in fields:
        doc = next((d for d in documents if d.id == f.document_id), None)
        if doc:
            field_map[(doc.doc_type, f.name)] = f

    for rule in cross_doc_rules:
        field_target = rule.get("field")
        sources = rule.get("sources", [])
        tolerance = rule.get("tolerance", 0)
        severity = rule.get("severity", "warning")
        is_fuzzy = rule.get("match") == "fuzzy"

        resolved_sources = []
        for src in sources:
            parts = src.split(".")
            if parts[0] == "app":
                # e.g. app.declared.land_area_acres or app.institution.name
                val = app_data
                for p in parts[1:]:
                    val = val.get(p) if isinstance(val, dict) else None
                if val is not None:
                    resolved_sources.append({
                        "source": src,
                        "value": val,
                        "document_id": None,
                        "doc_type": "application",
                        "page": 1,
                        "bbox": None,
                        "field": parts[-1]
                    })
            else:
                doc_type = parts[0]
                fname = parts[1]
                doc_rec = doc_map.get(doc_type)
                ef = field_map.get((doc_type, fname))
                if doc_rec and ef and ef.value not in (None, "null"):
                    bbox = None
                    if ef.bbox_json:
                        try:
                            bbox = json.loads(ef.bbox_json)
                        except Exception:
                            bbox = None
                    resolved_sources.append({
                        "source": src,
                        "value": ef.value,
                        "document_id": doc_rec.id,
                        "doc_type": doc_type,
                        "page": ef.page,
                        "bbox": bbox,
                        "field": fname
                    })

        if len(resolved_sources) < 2:
            continue

        # Check consistency across resolved sources
        has_mismatch = False
        mismatch_pair = None

        if is_fuzzy:
            # Fuzzy string comparison (rapidfuzz token_sort_ratio on normalised text)
            for i in range(len(resolved_sources)):
                for j in range(i + 1, len(resolved_sources)):
                    s1 = normalize_text_for_fuzzy(resolved_sources[i]["value"])
                    s2 = normalize_text_for_fuzzy(resolved_sources[j]["value"])
                    score = fuzz.token_sort_ratio(s1, s2)
                    if score < 90:
                        has_mismatch = True
                        mismatch_pair = (resolved_sources[i], resolved_sources[j])
                        break
                if has_mismatch:
                    break
        else:
            # Numeric / exact comparison
            for i in range(len(resolved_sources)):
                for j in range(i + 1, len(resolved_sources)):
                    v1 = resolved_sources[i]["value"]
                    v2 = resolved_sources[j]["value"]
                    try:
                        n1, n2 = float(v1), float(v2)
                        diff = abs(n1 - n2)
                        if diff > float(tolerance):
                            has_mismatch = True
                            mismatch_pair = (resolved_sources[i], resolved_sources[j])
                            break
                    except (ValueError, TypeError):
                        # String comparison
                        if str(v1).strip().lower() != str(v2).strip().lower():
                            has_mismatch = True
                            mismatch_pair = (resolved_sources[i], resolved_sources[j])
                            break
                if has_mismatch:
                    break

        if has_mismatch and mismatch_pair:
            # Create CROSS_DOC_MISMATCH finding with Section 4.3 evidence shape
            evidence_items = []
            for s in resolved_sources:
                evidence_items.append({
                    "document_id": s["document_id"],
                    "doc_type": s["doc_type"],
                    "page": s["page"],
                    "bbox": s["bbox"],
                    "field": s["field"],
                    "value": str(s["value"])
                })

            src1, src2 = mismatch_pair
            explanation = f"{field_target} differs between {src1['doc_type']} ({src1['value']}) and {src2['doc_type']} ({src2['value']})"

            evidence = {
                "items": evidence_items,
                "expected": "equal values",
                "method": "cross-document compare",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": explanation
            }

            f = Finding(
                application_id=app.id,
                document_id=src1["document_id"] or src2["document_id"],
                code="CROSS_DOC_MISMATCH",
                severity=severity,
                title=f"Cross-document mismatch on {field_target}",
                message=explanation,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            )
            findings.append(f)

    return findings

def run_aicte_record_checks(app: Application) -> List[Finding]:
    """
    (4) Records vs /mock/aicte -> RECORD_MISMATCH, NO_PREVIOUS_RECORD
    Uses ?no= query parameter when accessing /mock/aicte as instructed.
    """
    findings: List[Finding] = []
    if not app.aicte_id:
        return findings

    # Call /mock/aicte using ?no= query param (URL-encoded)
    from app.pipeline.verify import call_mock_api
    status_code, record = call_mock_api("/mock/aicte", {"no": app.aicte_id})
    if status_code == 404 or not record:
            evidence = {
                "items": [],
                "expected": f"AICTE record for {app.aicte_id} exists",
                "method": "aicte_records_lookup",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": f"Permanent ID {app.aicte_id} not found in AICTE registry."
            }
            f = Finding(
                application_id=app.id,
                document_id=None,
                code="NO_PREVIOUS_RECORD",
                severity="warning",
                title="No Previous AICTE Record Found",
                message=f"No previous AICTE record found for permanent ID {app.aicte_id}",
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            )
            findings.append(f)
            return findings

    if not record:
        return findings

    # Load application declared intake
    app_folder = settings.APPLICATIONS_DIR / app.folder
    declared = {}
    if (app_folder / "application.json").exists():
        try:
            with open(app_folder / "application.json", "r", encoding="utf-8") as f:
                app_data = json.load(f)
                declared = app_data.get("declared", {})
        except Exception:
            declared = {}

    prev_year = record.get("previous_year", {})
    if not prev_year:
        f = Finding(
            application_id=app.id,
            document_id=None,
            code="NO_PREVIOUS_RECORD",
            severity="warning",
            title="No Previous Year Approval Record",
            message=f"AICTE permanent ID {app.aicte_id} has no previous year approved record",
            confidence=1.0,
            evidence_json=json.dumps({"method": "aicte_records_lookup", "explanation": "previous_year block missing"}),
            status="open"
        )
        findings.append(f)
        return findings

    # Compare declared existing intake with sum of previous approved intake
    declared_existing_intake = declared.get("total_existing_intake")
    approved_intake_map = prev_year.get("approved_intake", {})
    approved_intake_sum = sum(approved_intake_map.values()) if isinstance(approved_intake_map, dict) else None

    if declared_existing_intake is not None and approved_intake_sum is not None:
        if int(declared_existing_intake) != int(approved_intake_sum):
            evidence = {
                "items": [{
                    "document_id": None,
                    "doc_type": "application",
                    "page": 1,
                    "bbox": None,
                    "field": "total_existing_intake",
                    "value": str(declared_existing_intake)
                }],
                "expected": f"total_existing_intake == {approved_intake_sum}",
                "method": "aicte_record_compare",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": f"Declared existing intake ({declared_existing_intake}) differs from previous year approved intake ({approved_intake_sum}) in AICTE record."
            }
            f = Finding(
                application_id=app.id,
                document_id=None,
                code="RECORD_MISMATCH",
                severity="critical",
                title="Existing Intake Mismatch with AICTE Record",
                message=f"Declared existing intake ({declared_existing_intake}) differs from previous year approved intake ({approved_intake_sum}) in AICTE records",
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            )
            findings.append(f)

    # Check TER payment
    ter_payment = record.get("ter_payment_2027_28", {})
    if ter_payment.get("status") != "PAID":
        evidence = {
            "items": [],
            "expected": "ter_payment status == PAID",
            "method": "aicte_ter_payment_check",
            "related_applications": [],
            "heatmap_url": None,
            "explanation": f"TER payment status is '{ter_payment.get('status')}' instead of 'PAID'."
        }
        f = Finding(
            application_id=app.id,
            document_id=None,
            code="RECORD_MISMATCH",
            severity="warning",
            title="TER Payment Not Paid",
            message=f"TER processing fee for academic year 2027-28 is not marked as PAID (status: {ter_payment.get('status')})",
            confidence=1.0,
            evidence_json=json.dumps(evidence),
            status="open"
        )
        findings.append(f)

    return findings

def run_all_checks(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField]
) -> List[Finding]:
    """Runs all checklist, validity, cross-document, and AICTE record checks."""
    all_findings: List[Finding] = []
    all_findings.extend(run_checklist_and_validity_checks(app, documents, fields))
    all_findings.extend(run_cross_document_checks(app, documents, fields))
    all_findings.extend(run_aicte_record_checks(app))
    return all_findings
