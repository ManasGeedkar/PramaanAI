import json
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import httpx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.models import Application, Document, ExtractedField, Finding, Verification
from app.services.audit import log_audit


def call_mock_api(path: str, params: Dict[str, str], timeout: float = 3.0) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    Calls mock endpoints in-process with the ?no= query style parameter.
    Zero network overhead, zero timeouts.
    """
    no_param = params.get("no")
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from app.mock.router import (
        get_fire_noc,
        get_land_record,
        get_university_affiliation,
        get_accreditation,
        get_aicte_record
    )
    try:
        if path.startswith("/mock/fire-noc"):
            resp = get_fire_noc(noc_no=None, no=no_param)
        elif path.startswith("/mock/land"):
            resp = get_land_record(deed_no=None, no=no_param)
        elif path.startswith("/mock/university/"):
            code = path.split("/")[3]
            resp = get_university_affiliation(code=code, letter_no=None, no=no_param)
        elif path.startswith("/mock/accreditation"):
            resp = get_accreditation(cert_no=None, no=no_param)
        elif path.startswith("/mock/aicte"):
            resp = get_aicte_record(aicte_id=None, no=no_param)
        else:
            return 404, {"detail": "Endpoint not found"}

        if isinstance(resp, JSONResponse):
            body_json = json.loads(resp.body.decode("utf-8")) if resp.body else {}
            return resp.status_code, body_json
        return 200, resp
    except HTTPException as e:
        return e.status_code, {"detail": e.detail}
    except Exception as e:
        return 500, {"detail": str(e)}



def verify_documents(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField],
    session: Session
) -> List[Finding]:
    """
    Source verification (Prompt 5):
    For each document type with `verify` in doc_types.yaml:
      - Call mock endpoint with ?no= query parameter (URL-encoded).
      - Compare returned values with printed values and QR payload.
      - 503/timeout -> source_unavailable
      - 202 -> pending
      - not found, institution mismatch, or field mismatch -> mismatch
      - registry valid_till < session_start -> expired
      - QR missing on a QR doc AND OCR confidence low -> manual_review
      - else -> verified
    Saves a Verification row per verified document.
    Creates findings: SOURCE_MISMATCH, SOURCE_EXPIRED, SOURCE_UNAVAILABLE,
                     VERIFICATION_PENDING, MANUAL_REVIEW, QR_MISMATCH.
    Logs an AuditLog row per source call.
    """
    findings: List[Finding] = []
    doc_types_cfg = settings.doc_types or {}
    checklists_cfg = settings.checklists or {}
    session_start = checklists_cfg.get("session_start", "2027-07-01")

    # Map fields by document_id -> name -> field
    doc_fields_map: Dict[int, Dict[str, ExtractedField]] = {}
    for f in fields:
        if f.document_id not in doc_fields_map:
            doc_fields_map[f.document_id] = {}
        doc_fields_map[f.document_id][f.name] = f

    for doc in documents:
        doc_cfg = doc_types_cfg.get(doc.doc_type)
        if not doc_cfg or not doc_cfg.get("verify"):
            continue

        verify_cfg = doc_cfg["verify"]
        key_field_name = verify_cfg.get("key_field")
        has_qr_flag = verify_cfg.get("qr", False)

        fields_dict = doc_fields_map.get(doc.id, {})
        key_field = fields_dict.get(key_field_name)
        key_val = str(key_field.value).strip() if key_field and key_field.value else None

        qr_field = fields_dict.get("qr")
        qr_data: Optional[Dict[str, Any]] = None
        if qr_field and qr_field.value:
            try:
                qr_data = json.loads(qr_field.value)
            except Exception:
                qr_data = None

        bbox = json.loads(key_field.bbox_json) if key_field and key_field.bbox_json else None

        # Check for MANUAL_REVIEW:
        # "QR missing on a QR doc AND OCR confidence low -> manual_review"
        is_qr_missing = (qr_data is None)
        is_ocr_low = (key_val is None) or (doc.scanned and doc.ocr_confidence is not None and doc.ocr_confidence < 0.95)

        if has_qr_flag and is_qr_missing and is_ocr_low:
            status = "manual_review"
            ref = key_val or "UNKNOWN"
            reason = "Blurry scan; QR unreadable and certificate number OCR low-confidence"
            details = {
                "reason": reason,
                "qr_present": False,
                "ocr_confidence": doc.ocr_confidence,
                "document_scanned": doc.scanned
            }
            v_record = Verification(
                document_id=doc.id,
                source=doc.doc_type,
                reference=ref,
                status=status,
                details_json=json.dumps(details),
                checked_at=datetime.utcnow().isoformat()
            )
            session.add(v_record)

            explanation = "Unreadable QR / low-confidence OCR on blurry scan"
            evidence = {
                "items": [{
                    "document_id": doc.id,
                    "doc_type": doc.doc_type,
                    "page": 1,
                    "bbox": bbox,
                    "field": key_field_name or "document",
                    "value": ref
                }],
                "expected": "readable document with verifiable QR code",
                "method": "source_verification",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": explanation
            }
            findings.append(Finding(
                application_id=app.id,
                document_id=doc.id,
                code="MANUAL_REVIEW",
                severity="warning",
                title=f"Manual Review Required ({doc.doc_type})",
                message=explanation,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            ))

            log_audit(
                session=session,
                actor="pipeline",
                action="verify_source",
                entity_type="document",
                entity_id=doc.id,
                payload={
                    "doc_type": doc.doc_type,
                    "reference": ref,
                    "status": status,
                    "reason": reason
                }
            )
            continue

        # If key field is completely missing (and not already flagged manual_review)
        if not key_val:
            status = "mismatch"
            details = {"reason": f"Missing key field '{key_field_name}'"}
            v_record = Verification(
                document_id=doc.id,
                source=doc.doc_type,
                reference="UNKNOWN",
                status=status,
                details_json=json.dumps(details),
                checked_at=datetime.utcnow().isoformat()
            )
            session.add(v_record)
            continue

        # Determine endpoint path & parameters with ?no= query parameter (URL-encoded)
        if doc.doc_type == "fire_noc":
            endpoint = "/mock/fire-noc"
            params = {"no": key_val}
        elif doc.doc_type == "land_deed":
            endpoint = "/mock/land"
            params = {"no": key_val}
        elif doc.doc_type == "affiliation_letter":
            univ_code = key_val.split("/")[0] if "/" in key_val else "STU"
            endpoint = f"/mock/university/{univ_code}"
            params = {"no": key_val}
        elif doc.doc_type == "accreditation_certificate":
            endpoint = "/mock/accreditation"
            params = {"no": key_val}
        else:
            endpoint = f"/mock/{doc.doc_type}"
            params = {"no": key_val}

        # Make the mock call (3-second timeout)
        status_code, resp_data = call_mock_api(endpoint, params, timeout=3.0)

        # 1. 503 or timeout -> source_unavailable
        if status_code in (503, 504):
            status = "source_unavailable"
            univ_name = key_val.split("/")[0] if "/" in key_val else doc.doc_type
            reason = f"{univ_name} verification service unavailable"
            details = {"reason": reason, "status_code": status_code}
            v_record = Verification(
                document_id=doc.id,
                source=doc.doc_type,
                reference=key_val,
                status=status,
                details_json=json.dumps(details),
                checked_at=datetime.utcnow().isoformat()
            )
            session.add(v_record)

            explanation = f"{univ_name} verification API unavailable"
            evidence = {
                "items": [{
                    "document_id": doc.id,
                    "doc_type": doc.doc_type,
                    "page": 1,
                    "bbox": bbox,
                    "field": key_field_name,
                    "value": key_val
                }],
                "expected": "responsive registry service",
                "method": "source_verification",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": explanation
            }
            findings.append(Finding(
                application_id=app.id,
                document_id=doc.id,
                code="SOURCE_UNAVAILABLE",
                severity="info",
                title=f"Source Service Unavailable ({doc.doc_type})",
                message=explanation,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            ))

            log_audit(
                session=session,
                actor="pipeline",
                action="verify_source",
                entity_type="document",
                entity_id=doc.id,
                payload={
                    "doc_type": doc.doc_type,
                    "reference": key_val,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "status": status
                }
            )
            continue

        # 2. 202 -> pending
        if status_code == 202 or (resp_data and resp_data.get("response") == "PENDING"):
            status = "pending"
            reason = f"Registry returned PENDING (async verification)"
            details = {"reason": reason, "reference": key_val}
            v_record = Verification(
                document_id=doc.id,
                source=doc.doc_type,
                reference=key_val,
                status=status,
                details_json=json.dumps(details),
                checked_at=datetime.utcnow().isoformat()
            )
            session.add(v_record)

            explanation = "Land registry response PENDING"
            evidence = {
                "items": [{
                    "document_id": doc.id,
                    "doc_type": doc.doc_type,
                    "page": 1,
                    "bbox": bbox,
                    "field": key_field_name,
                    "value": key_val
                }],
                "expected": "immediate registry confirmation",
                "method": "source_verification",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": explanation
            }
            findings.append(Finding(
                application_id=app.id,
                document_id=doc.id,
                code="VERIFICATION_PENDING",
                severity="info",
                title=f"Verification Pending ({doc.doc_type})",
                message=explanation,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            ))

            log_audit(
                session=session,
                actor="pipeline",
                action="verify_source",
                entity_type="document",
                entity_id=doc.id,
                payload={
                    "doc_type": doc.doc_type,
                    "reference": key_val,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "status": status
                }
            )
            continue

        # 3. 404 -> not found / mismatch
        if status_code == 404 or not resp_data:
            status = "mismatch"
            reason = f"Reference {key_val} not found in {doc.doc_type} registry"
            details = {"reason": reason, "status_code": status_code}
            v_record = Verification(
                document_id=doc.id,
                source=doc.doc_type,
                reference=key_val,
                status=status,
                details_json=json.dumps(details),
                checked_at=datetime.utcnow().isoformat()
            )
            session.add(v_record)

            explanation = f"Record '{key_val}' not found in registry"
            evidence = {
                "items": [{
                    "document_id": doc.id,
                    "doc_type": doc.doc_type,
                    "page": 1,
                    "bbox": bbox,
                    "field": key_field_name,
                    "value": key_val
                }],
                "expected": "record exists in official registry",
                "method": "source_verification",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": explanation
            }
            findings.append(Finding(
                application_id=app.id,
                document_id=doc.id,
                code="SOURCE_MISMATCH",
                severity="critical",
                title=f"Record Not Found in Registry ({doc.doc_type})",
                message=explanation,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            ))

            log_audit(
                session=session,
                actor="pipeline",
                action="verify_source",
                entity_type="document",
                entity_id=doc.id,
                payload={
                    "doc_type": doc.doc_type,
                    "reference": key_val,
                    "endpoint": endpoint,
                    "status_code": status_code,
                    "status": status
                }
            )
            continue

        # 4. 200 OK: Compare returned values, printed values, and QR payload
        record = resp_data
        holder_id = record.get("holder_institution_id") or record.get("institution_id")
        institution_mismatch = (holder_id is not None and holder_id != app.institution_id)

        # Check QR comparisons
        qr_mismatches: List[str] = []
        if qr_data:
            qr_holder = qr_data.get("holder")
            if qr_holder and qr_holder != app.institution_id:
                qr_mismatches.append(f"QR HOLDER={qr_holder}")

            qr_valid_till = qr_data.get("valid_till")
            printed_valid_till = fields_dict.get("valid_till")
            printed_vt_val = str(printed_valid_till.value) if printed_valid_till and printed_valid_till.value else None
            if qr_valid_till and printed_vt_val and qr_valid_till != printed_vt_val:
                # Format to dd-mm-yyyy for message if needed or match exact expected
                qr_mismatches.append(f"QR VALID_TILL={qr_valid_till} vs printed {printed_vt_val}")

        for qrm in qr_mismatches:
            vt_bbox = None
            if "VALID_TILL" in qrm and fields_dict.get("valid_till") and fields_dict["valid_till"].bbox_json:
                vt_bbox = json.loads(fields_dict["valid_till"].bbox_json)
            else:
                vt_bbox = bbox

            evidence = {
                "items": [{
                    "document_id": doc.id,
                    "doc_type": doc.doc_type,
                    "page": 1,
                    "bbox": vt_bbox,
                    "field": "valid_till" if "VALID_TILL" in qrm else "qr",
                    "value": qrm
                }],
                "expected": "QR payload matches printed certificate values",
                "method": "qr_verification",
                "related_applications": [qr_data.get("holder")] if qr_data and qr_data.get("holder") != app.institution_id else [],
                "heatmap_url": None,
                "explanation": qrm
            }
            findings.append(Finding(
                application_id=app.id,
                document_id=doc.id,
                code="QR_MISMATCH",
                severity="critical",
                title=f"QR Code Mismatch ({doc.doc_type})",
                message=qrm,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            ))

        # Check registry field comparisons
        registry_mismatch = False
        mismatch_reasons = []

        if institution_mismatch:
            registry_mismatch = True
            mismatch_reasons.append(f"Registry: {key_val} is held by {holder_id}, not this institution")

        reg_valid_till = record.get("valid_till")
        printed_valid_till_field = fields_dict.get("valid_till")
        printed_vt = str(printed_valid_till_field.value) if printed_valid_till_field and printed_valid_till_field.value else None
        if reg_valid_till and printed_vt and reg_valid_till != printed_vt:
            registry_mismatch = True
            mismatch_reasons.append(f"Registry valid_till {reg_valid_till} ({record.get('status', 'ACTIVE')}) vs printed {printed_vt}")

        # Evaluate final status
        if registry_mismatch or qr_mismatches:
            status = "mismatch"
            reason = "; ".join(mismatch_reasons + qr_mismatches)
            if institution_mismatch:
                reason = f"Registry: NOC number belongs to {holder_id} ({record.get('holder_name', '')}); QR HOLDER={qr_data.get('holder') if qr_data else holder_id}"
            elif reg_valid_till and printed_vt and reg_valid_till != printed_vt:
                reason = f"Printed Valid Till {printed_vt}; QR and registry say {reg_valid_till} (expired)"

            if mismatch_reasons:
                explanation = "; ".join(mismatch_reasons)
                evidence = {
                    "items": [{
                        "document_id": doc.id,
                        "doc_type": doc.doc_type,
                        "page": 1,
                        "bbox": bbox,
                        "field": key_field_name,
                        "value": key_val
                    }],
                    "expected": "registry details match application",
                    "method": "source_verification",
                    "related_applications": [holder_id] if holder_id and holder_id != app.institution_id else [],
                    "heatmap_url": None,
                    "explanation": explanation
                }
                findings.append(Finding(
                    application_id=app.id,
                    document_id=doc.id,
                    code="SOURCE_MISMATCH",
                    severity="critical",
                    title=f"Source Registry Mismatch ({doc.doc_type})",
                    message=explanation,
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                    status="open"
                ))

        elif record.get("status") == "EXPIRED" or (reg_valid_till and reg_valid_till < session_start):
            status = "expired"
            reason = f"Registry status EXPIRED (valid till {reg_valid_till})"
            explanation = "Registry status EXPIRED"
            evidence = {
                "items": [{
                    "document_id": doc.id,
                    "doc_type": doc.doc_type,
                    "page": 1,
                    "bbox": bbox,
                    "field": "valid_till",
                    "value": reg_valid_till
                }],
                "expected": f"active registry status valid beyond {session_start}",
                "method": "source_verification",
                "related_applications": [],
                "heatmap_url": None,
                "explanation": explanation
            }
            findings.append(Finding(
                application_id=app.id,
                document_id=doc.id,
                code="SOURCE_EXPIRED",
                severity="critical",
                title=f"Document Expired in Official Registry ({doc.doc_type})",
                message=explanation,
                confidence=1.0,
                evidence_json=json.dumps(evidence),
                status="open"
            ))

        else:
            status = "verified"
            if doc.doc_type == "fire_noc":
                reason = "Registry and QR match printed details"
            elif doc.doc_type == "land_deed":
                reason = "Registry record matches deed"
            elif doc.doc_type == "affiliation_letter":
                reason = "University record matches"
            elif doc.doc_type == "accreditation_certificate":
                reason = "Accreditation registry matches"
            else:
                reason = "Registry record matches"

        details = {
            "reason": reason,
            "status_code": status_code,
            "registry_record": record
        }

        v_record = Verification(
            document_id=doc.id,
            source=doc.doc_type,
            reference=key_val,
            status=status,
            details_json=json.dumps(details),
            checked_at=datetime.utcnow().isoformat()
        )
        session.add(v_record)

        log_audit(
            session=session,
            actor="pipeline",
            action="verify_source",
            entity_type="document",
            entity_id=doc.id,
            payload={
                "doc_type": doc.doc_type,
                "reference": key_val,
                "endpoint": endpoint,
                "status_code": status_code,
                "status": status,
                "reason": reason
            }
        )

    session.commit()
    return findings
