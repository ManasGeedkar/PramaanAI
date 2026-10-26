import time
from typing import Dict, Any, List
from sqlmodel import Session, select
from app.models import Application, Document, ExtractedField, Finding, Verification, Review
from app.pipeline.extract import extract_document
from app.pipeline.quality import assess_document_quality, check_low_ocr_confidence_fields
from app.pipeline.checks import run_all_checks
from app.pipeline.rules import evaluate_rules
from app.pipeline.forensics import run_all_forensics
from app.pipeline.verify import verify_documents
from app.pipeline.entities import register_application_entities, detect_entity_reuse, refresh_related_applications
from app.pipeline.risk import calculate_risk
from app.services.audit import log_audit

def run_pipeline(application_id: int, session: Session) -> Dict[str, Any]:
    """
    Runs the scrutiny pipeline for a single application in order:
    extract -> quality -> checks -> rules -> forensics -> verify -> entities -> risk
    Idempotent: replaces previous extracted fields, findings, and verifications for this application.
    """
    app = session.get(Application, application_id)
    if not app:
        raise ValueError(f"Application {application_id} not found")

    docs = session.exec(
        select(Document).where(Document.application_id == app.id)
    ).all()

    doc_ids = [d.id for d in docs]

    # Delete previous extracted fields, verifications, and findings for idempotency
    if doc_ids:
        existing_fields = session.exec(
            select(ExtractedField).where(ExtractedField.document_id.in_(doc_ids))
        ).all()
        for f in existing_fields:
            session.delete(f)

        existing_verifs = session.exec(
            select(Verification).where(Verification.document_id.in_(doc_ids))
        ).all()
        for v in existing_verifs:
            session.delete(v)

    existing_findings = session.exec(
        select(Finding).where(Finding.application_id == app.id)
    ).all()
    finding_ids = [f.id for f in existing_findings if f.id is not None]
    if finding_ids:
        existing_reviews = session.exec(
            select(Review).where(Review.finding_id.in_(finding_ids))
        ).all()
        for r in existing_reviews:
            session.delete(r)

    for f in existing_findings:
        session.delete(f)

    session.commit()

    all_extracted: List[ExtractedField] = []
    all_findings: List[Finding] = []
    stage_times: Dict[str, float] = {
        "extract": 0.0,
        "quality": 0.0,
        "checks": 0.0,
        "rules": 0.0,
        "forensics": 0.0,
        "verify": 0.0,
        "entities": 0.0,
        "risk": 0.0
    }

    # 1. Extract stage
    t0 = time.perf_counter()
    for doc in docs:
        fields = extract_document(doc, session)
        for f in fields:
            session.add(f)
            all_extracted.append(f)
    session.commit()
    stage_times["extract"] = round(time.perf_counter() - t0, 3)

    # 2. Quality stage (scan blur, DPI, contrast & OCR confidence check)
    t0 = time.perf_counter()
    for doc in docs:
        doc_fields = [f for f in all_extracted if f.document_id == doc.id]
        quality_data, quality_findings = assess_document_quality(doc, session)
        for qf in quality_findings:
            session.add(qf)
            all_findings.append(qf)

        ocr_findings = check_low_ocr_confidence_fields(doc, doc_fields, session)
        for of in ocr_findings:
            session.add(of)
            all_findings.append(of)
    session.commit()
    stage_times["quality"] = round(time.perf_counter() - t0, 3)

    # 3. Checks stage (checklist, expiry, cross-doc consistency, AICTE records)
    t0 = time.perf_counter()
    check_findings = run_all_checks(app, docs, all_extracted)
    for cf in check_findings:
        session.add(cf)
        all_findings.append(cf)
    stage_times["checks"] = round(time.perf_counter() - t0, 3)

    # 4. Rules stage (json-logic compliance rules)
    t0 = time.perf_counter()
    rule_findings = evaluate_rules(app, docs, all_extracted, session)
    for rf in rule_findings:
        session.add(rf)
        all_findings.append(rf)
    stage_times["rules"] = round(time.perf_counter() - t0, 3)

    # 5. Forensics stage (ELA tamper detection, PDF metadata anomaly, pHash duplicate photos)
    t0 = time.perf_counter()
    forensics_findings = run_all_forensics(app, docs, all_extracted, session)
    for ff in forensics_findings:
        session.add(ff)
        all_findings.append(ff)
    session.commit()
    stage_times["forensics"] = round(time.perf_counter() - t0, 3)

    # 6. Verify stage (mock registries and QR verification with 6 statuses)
    t0 = time.perf_counter()
    verify_findings = verify_documents(app, docs, all_extracted, session)
    for vf in verify_findings:
        session.add(vf)
        all_findings.append(vf)
    session.commit()
    stage_times["verify"] = round(time.perf_counter() - t0, 3)

    # 7. Entities stage (register entities, detect reuse, refresh related applications)
    t0 = time.perf_counter()
    register_application_entities(app, docs, all_extracted, session)
    entity_findings = detect_entity_reuse(app, docs, session)
    for ef in entity_findings:
        session.add(ef)
        all_findings.append(ef)
    session.commit()

    # Refresh other applications sharing entities or photos immediately (two-pass fix)
    refreshed_other_apps = refresh_related_applications(app, session)
    stage_times["entities"] = round(time.perf_counter() - t0, 3)

    # 8. Risk stage (triage score, band, and breakdown per risk.yaml)
    t0 = time.perf_counter()
    calculate_risk(app, session)
    stage_times["risk"] = round(time.perf_counter() - t0, 3)

    app.status = "validated"
    session.add(app)
    session.commit()
    session.refresh(app)

    # Log audit entry
    log_audit(
        session=session,
        actor="pipeline",
        action="scrutiny_complete",
        entity_type="application",
        entity_id=app.id,
        payload={
            "application_no": app.application_no,
            "status": app.status,
            "risk_score": app.risk_score,
            "risk_band": app.risk_band,
            "documents_count": len(docs),
            "findings_count": len(all_findings),
            "refreshed_related_applications": refreshed_other_apps,
            "stage_times": stage_times
        }
    )

    total_pipeline_time = round(sum(stage_times.values()), 3)

    return {
        "application_id": app.id,
        "application_no": app.application_no,
        "status": app.status,
        "risk_score": app.risk_score,
        "risk_band": app.risk_band,
        "documents_processed": len(docs),
        "fields_extracted": len(all_extracted),
        "findings_count": len(all_findings),
        "stage_times": stage_times,
        "total_time": total_pipeline_time
    }


