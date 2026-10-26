import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from PIL import Image
import imagehash
from sqlmodel import Session, select

from app.config import DATA_DIR
from app.models import Application, Document, ExtractedField, Finding, Entity, EntityOccurrence, Verification

def get_or_create_entity(entity_type: str, key: str, display: str, session: Session) -> Entity:
    """Finds existing Entity by (entity_type, key) or creates a new one."""
    entity = session.exec(
        select(Entity).where(Entity.entity_type == entity_type, Entity.key == key)
    ).first()
    if not entity:
        entity = Entity(entity_type=entity_type, key=key, display=display)
        session.add(entity)
        session.commit()
        session.refresh(entity)
    return entity

def register_application_entities(
    app: Application,
    documents: List[Document],
    fields: List[ExtractedField],
    session: Session
) -> None:
    """
    Extracts entities (faculty, fire_noc_no, deed_no, survey_no, photo)
    from an application's documents and records EntityOccurrence rows.
    Idempotent: removes prior EntityOccurrence rows for this application.
    """
    # Delete prior occurrences for this application
    prior_occs = session.exec(
        select(EntityOccurrence).where(EntityOccurrence.application_id == app.id)
    ).all()
    for occ in prior_occs:
        session.delete(occ)
    session.commit()

    doc_map = {d.id: d for d in documents}

    for f in fields:
        doc = doc_map.get(f.document_id)
        if not doc:
            continue

        # 1. Faculty (from faculty_list rows)
        if doc.doc_type == "faculty_list" and f.name == "rows" and f.value:
            try:
                faculty_rows = json.loads(f.value)
                for r in faculty_rows:
                    fac_id = str(r.get("faculty_id", "")).strip()
                    name = str(r.get("name", "")).strip()
                    dob = str(r.get("dob", "")).strip()
                    bbox = r.get("bbox")

                    if fac_id and dob:
                        # Key matches faculty_id AND dob per specification
                        key = f"{fac_id}_{dob}"
                        display = f"{name} ({fac_id})"
                        ent = get_or_create_entity("faculty", key, display, session)
                        occ = EntityOccurrence(
                            entity_id=ent.id,
                            application_id=app.id,
                            document_id=doc.id,
                            academic_year=app.academic_year,
                            bbox_json=json.dumps(bbox) if bbox else None
                        )
                        session.add(occ)
            except Exception as e:
                print(f"Error parsing faculty rows for doc {doc.id}: {e}")

        # 2. Fire NOC Number
        elif doc.doc_type == "fire_noc" and f.name == "noc_no" and f.value:
            noc_no = str(f.value).strip()
            ent = get_or_create_entity("fire_noc_no", noc_no, f"NOC {noc_no}", session)
            occ = EntityOccurrence(
                entity_id=ent.id,
                application_id=app.id,
                document_id=doc.id,
                academic_year=app.academic_year,
                bbox_json=f.bbox_json
            )
            session.add(occ)

        # 3. Sale Deed Number
        elif doc.doc_type == "land_deed" and f.name == "deed_no" and f.value:
            deed_no = str(f.value).strip()
            ent = get_or_create_entity("deed_no", deed_no, f"Sale Deed {deed_no}", session)
            occ = EntityOccurrence(
                entity_id=ent.id,
                application_id=app.id,
                document_id=doc.id,
                academic_year=app.academic_year,
                bbox_json=f.bbox_json
            )
            session.add(occ)

        # 4. Survey Number
        elif doc.doc_type == "land_deed" and f.name == "survey_no" and f.value:
            survey_no = str(f.value).strip()
            ent = get_or_create_entity("survey_no", survey_no, f"Survey {survey_no}", session)
            occ = EntityOccurrence(
                entity_id=ent.id,
                application_id=app.id,
                document_id=doc.id,
                academic_year=app.academic_year,
                bbox_json=f.bbox_json
            )
            session.add(occ)

    # 5. Photos (pHash entities for entity graph)
    from app.pipeline.forensics import get_photo_phash
    for doc in documents:
        if doc.doc_type.startswith("photo") or Path(doc.file_path).suffix.lower() in [".jpg", ".jpeg", ".png"]:
            try:
                h = get_photo_phash(doc)
                if h is not None:
                    h_str = str(h)
                    # Check if any existing photo entity is a near-duplicate (Hamming distance <= 6)
                    existing_photo_entities = session.exec(
                        select(Entity).where(Entity.entity_type == "photo")
                    ).all()
                    matched_ent = None
                    for ep in existing_photo_entities:
                        try:
                            ep_hash = imagehash.hex_to_hash(ep.key)
                            if (h - ep_hash) <= 6:
                                matched_ent = ep
                                break
                        except Exception:
                            pass

                    if matched_ent:
                        ent = matched_ent
                    else:
                        is_lab = "lab" in Path(doc.file_path).name.lower() or "lab" in doc.doc_type.lower()
                        clean_name = "Lab Photo" if is_lab else Path(doc.file_path).stem.replace('_', ' ').title()
                        ent = get_or_create_entity("photo", h_str, f"{clean_name} ({Path(doc.file_path).name})", session)

                    occ = EntityOccurrence(
                        entity_id=ent.id,
                        application_id=app.id,
                        document_id=doc.id,
                        academic_year=app.academic_year,
                        bbox_json=None
                    )
                    session.add(occ)
            except Exception:
                pass

    session.commit()

def detect_entity_reuse(
    app: Application,
    documents: List[Document],
    session: Session
) -> List[Finding]:
    """
    Checks for cross-application entity reuse within the same academic year.
    Generates ENTITY_REUSE findings.
    Genuine holder is determined from the Verification row (status verified).
    """
    findings: List[Finding] = []
    doc_map = {d.id: d for d in documents}

    # Query this application's occurrences
    app_occs = session.exec(
        select(EntityOccurrence).where(EntityOccurrence.application_id == app.id)
    ).all()

    # Track faculty reuse grouped by other application
    faculty_shared: Dict[int, List[Dict[str, Any]]] = {}

    for occ in app_occs:
        entity = session.get(Entity, occ.entity_id)
        if not entity:
            continue

        # Photos appear in graph but do NOT create ENTITY_REUSE (DUPLICATE_IMAGE covers them)
        if entity.entity_type == "photo":
            continue

        # Find occurrences in other applications of the same academic year
        other_occs = session.exec(
            select(EntityOccurrence).where(
                EntityOccurrence.entity_id == entity.id,
                EntityOccurrence.application_id != app.id,
                EntityOccurrence.academic_year == app.academic_year
            )
        ).all()

        if not other_occs:
            continue

        doc = doc_map.get(occ.document_id)

        # Faculty: group across the shared pair of applications
        if entity.entity_type == "faculty":
            fac_id = entity.key.split("_")[0]
            for o in other_occs:
                if o.application_id not in faculty_shared:
                    faculty_shared[o.application_id] = []
                faculty_shared[o.application_id].append({
                    "entity": entity,
                    "fac_id": fac_id,
                    "doc": doc,
                    "occ": occ
                })
            continue

        # Fire NOC Number
        elif entity.entity_type == "fire_noc_no":
            noc_no = entity.key
            # Decide genuine holder from Verification row (status verified), not from registry directly
            app_verif = session.exec(
                select(Verification).where(
                    Verification.document_id == occ.document_id,
                    Verification.status == "verified"
                )
            ).first()
            is_genuine = (app_verif is not None)

            for o in other_occs:
                other_app = session.get(Application, o.application_id)
                if not other_app:
                    continue

                if is_genuine:
                    severity = "info"
                    explanation = f"NOC number {noc_no} also appears in {other_app.institution_id} ({app.institution_id} is the genuine holder per registry)"
                    title = "NOC Number Mentioned in Another Application"
                else:
                    severity = "critical"
                    explanation = f"Same Fire NOC number in {other_app.institution_id} application"
                    title = "Reused Fire NOC Number"

                bbox = json.loads(occ.bbox_json) if occ.bbox_json else None
                evidence = {
                    "items": [{
                        "document_id": occ.document_id,
                        "doc_type": "fire_noc",
                        "page": 1,
                        "bbox": bbox,
                        "field": "noc_no",
                        "value": noc_no
                    }],
                    "expected": "unique certificate holder",
                    "method": "entity_graph",
                    "related_applications": [other_app.institution_id],
                    "heatmap_url": None,
                    "explanation": explanation
                }
                findings.append(Finding(
                    application_id=app.id,
                    document_id=occ.document_id,
                    code="ENTITY_REUSE",
                    severity=severity,
                    title=title,
                    message=explanation,
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                    status="open"
                ))

        # Sale Deed Number
        elif entity.entity_type == "deed_no":
            deed_no = entity.key
            # Decide genuine holder from Verification row (status verified), not from registry directly
            app_verif = session.exec(
                select(Verification).where(
                    Verification.document_id == occ.document_id,
                    Verification.status == "verified"
                )
            ).first()
            is_genuine = (app_verif is not None)

            for o in other_occs:
                other_app = session.get(Application, o.application_id)
                if not other_app:
                    continue

                severity = "info" if is_genuine else "critical"
                explanation = f"Same land deed number {deed_no} in {other_app.institution_id} application"
                bbox = json.loads(occ.bbox_json) if occ.bbox_json else None
                evidence = {
                    "items": [{
                        "document_id": occ.document_id,
                        "doc_type": "land_deed",
                        "page": 1,
                        "bbox": bbox,
                        "field": "deed_no",
                        "value": deed_no
                    }],
                    "expected": "unique deed number",
                    "method": "entity_graph",
                    "related_applications": [other_app.institution_id],
                    "heatmap_url": None,
                    "explanation": explanation
                }
                findings.append(Finding(
                    application_id=app.id,
                    document_id=occ.document_id,
                    code="ENTITY_REUSE",
                    severity=severity,
                    title="Land Deed Mentioned in Another Application" if is_genuine else "Reused Land Deed Number",
                    message=explanation,
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                    status="open"
                ))

        # Survey Number
        elif entity.entity_type == "survey_no":
            survey_no = entity.key
            for o in other_occs:
                other_app = session.get(Application, o.application_id)
                if not other_app:
                    continue

                explanation = f"Same survey number {survey_no} in {other_app.institution_id} application"
                bbox = json.loads(occ.bbox_json) if occ.bbox_json else None
                evidence = {
                    "items": [{
                        "document_id": occ.document_id,
                        "doc_type": "land_deed",
                        "page": 1,
                        "bbox": bbox,
                        "field": "survey_no",
                        "value": survey_no
                    }],
                    "expected": "unique survey number",
                    "method": "entity_graph",
                    "related_applications": [other_app.institution_id],
                    "heatmap_url": None,
                    "explanation": explanation
                }
                findings.append(Finding(
                    application_id=app.id,
                    document_id=occ.document_id,
                    code="ENTITY_REUSE",
                    severity="warning",
                    title="Survey Number Reuse",
                    message=explanation,
                    confidence=1.0,
                    evidence_json=json.dumps(evidence),
                    status="open"
                ))

    # Process grouped faculty findings
    for other_app_id, fac_items in faculty_shared.items():
        other_app = session.get(Application, other_app_id)
        if not other_app:
            continue

        unique_fac_ids = sorted(list({item["fac_id"] for item in fac_items}))
        fac_count = len(unique_fac_ids)
        explanation = f"{fac_count} faculty (same Faculty ID + name + DOB) also on {other_app.institution_id} list for {app.academic_year}"

        evidence_items = []
        doc_id = fac_items[0]["doc"].id if fac_items[0]["doc"] else None
        for item in fac_items:
            occ = item["occ"]
            bbox = json.loads(occ.bbox_json) if occ.bbox_json else None
            evidence_items.append({
                "document_id": occ.document_id,
                "doc_type": "faculty_list",
                "page": 1,
                "bbox": bbox,
                "field": "faculty",
                "value": item["entity"].display
            })

        evidence = {
            "items": evidence_items,
            "expected": "exclusive faculty employment",
            "method": "entity_graph",
            "related_applications": [other_app.institution_id],
            "entity_ids": unique_fac_ids,
            "heatmap_url": None,
            "explanation": explanation
        }
        findings.append(Finding(
            application_id=app.id,
            document_id=doc_id,
            code="ENTITY_REUSE",
            severity="warning",
            title=f"Faculty Reuse Across Applications ({fac_count} faculty)",
            message=explanation,
            confidence=1.0,
            evidence_json=json.dumps(evidence),
            status="open"
        ))

    return findings

def refresh_related_applications(app: Application, session: Session, visited: Optional[Set[int]] = None) -> List[int]:
    """
    Fixes two-pass entity stage requirement:
    After entities stage for application X, finds every other application that shares
    an entity (faculty, fire_noc_no, deed_no, survey_no, photo) with X and refreshes
    only their ENTITY_REUSE and DUPLICATE_IMAGE findings and their risk score from data
    already in the DB. No OCR, QR, ELA or verification calls, and no cascading refreshes.
    """
    from app.pipeline.forensics import run_phash_analysis
    from app.pipeline.risk import calculate_risk

    if visited is None:
        visited = set()
    visited.add(app.id)

    # 1. Find all entity IDs for application X
    app_occs = session.exec(
        select(EntityOccurrence).where(EntityOccurrence.application_id == app.id)
    ).all()
    entity_ids = {occ.entity_id for occ in app_occs}

    other_app_ids: Set[int] = set()
    if entity_ids:
        other_occs = session.exec(
            select(EntityOccurrence).where(
                EntityOccurrence.entity_id.in_(entity_ids),
                EntityOccurrence.application_id != app.id
            )
        ).all()
        for o in other_occs:
            if o.application_id not in visited:
                other_app_ids.add(o.application_id)

    # 2. Check for duplicate photos from existing DUPLICATE_IMAGE findings in the DB
    dup_findings = session.exec(
        select(Finding).where(
            Finding.application_id == app.id,
            Finding.code == "DUPLICATE_IMAGE"
        )
    ).all()
    for df in dup_findings:
        if df.evidence_json:
            try:
                ev = json.loads(df.evidence_json)
                for rel_inst in ev.get("related_applications", []):
                    rel_app = session.exec(
                        select(Application).where(Application.institution_id == rel_inst)
                    ).first()
                    if rel_app and rel_app.id != app.id and rel_app.id not in visited:
                        other_app_ids.add(rel_app.id)
            except Exception:
                pass

    refreshed_ids: List[int] = []
    for other_id in other_app_ids:
        other_app = session.get(Application, other_id)
        if not other_app:
            continue

        other_docs = session.exec(
            select(Document).where(Document.application_id == other_app.id)
        ).all()

        # Delete ONLY ENTITY_REUSE and DUPLICATE_IMAGE findings for other_app
        old_findings = session.exec(
            select(Finding).where(
                Finding.application_id == other_app.id,
                Finding.code.in_(["ENTITY_REUSE", "DUPLICATE_IMAGE"])
            )
        ).all()
        for of in old_findings:
            session.delete(of)
        session.commit()

        # Re-run ENTITY_REUSE
        new_entity_findings = detect_entity_reuse(other_app, other_docs, session)
        for nef in new_entity_findings:
            session.add(nef)

        # Re-run DUPLICATE_IMAGE (uses cached pHash, zero disk overhead)
        for odoc in other_docs:
            if odoc.doc_type.startswith("photo") or Path(odoc.file_path).suffix.lower() in [".jpg", ".jpeg", ".png"]:
                try:
                    p_findings = run_phash_analysis(other_app, odoc, session)
                    for pf in p_findings:
                        session.add(pf)
                except Exception:
                    pass

        session.commit()

        # Refresh risk score immediately
        calculate_risk(other_app, session)
        refreshed_ids.append(other_app.id)

    return refreshed_ids

