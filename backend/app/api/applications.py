import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Form, File, UploadFile, Body
from sqlmodel import Session, select
from app.db import get_session
from app.models import Application, Document, Finding, ExtractedField, Verification

router = APIRouter(prefix="/api/applications", tags=["applications"])

@router.get("")
def list_applications(
    sort: Optional[str] = Query(default=None),
    session: Session = Depends(get_session)
):
    query = select(Application)
    applications = session.exec(query).all()

    # Hide INST04 if DEMO_LIVE_UPLOAD is set (for live video demo recording)
    if os.environ.get("DEMO_LIVE_UPLOAD") == "1":
        applications = [app for app in applications if app.institution_id != "INST04"]

    results = []
    for app in applications:
        # Calculate severity counts from findings
        findings = session.exec(select(Finding).where(Finding.application_id == app.id)).all()
        counts = {
            "critical": sum(1 for f in findings if f.severity == "critical"),
            "warning": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
        }

        risk_breakdown = []
        if app.risk_breakdown_json:
            try:
                risk_breakdown = json.loads(app.risk_breakdown_json)
            except Exception:
                risk_breakdown = []

        results.append({
            "id": app.id,
            "no": app.application_no,
            "application_no": app.application_no,
            "institution_id": app.institution_id,
            "institution": app.institution_name,
            "institution_name": app.institution_name,
            "aicte_id": app.aicte_id,
            "category": app.category,
            "academic_year": app.academic_year,
            "submitted_on": app.submitted_on,
            "status": app.status,
            "risk_band": app.risk_band or "Low",
            "risk_score": app.risk_score,
            "risk_breakdown": risk_breakdown,
            "counts": counts,
            "folder": app.folder,
            "created_at": app.created_at,
        })

    if sort == "risk":
        results.sort(key=lambda x: x["risk_score"], reverse=True)
    else:
        results.sort(key=lambda x: x["id"])

    return results

@router.get("/{id}")
def get_application(
    id: int,
    session: Session = Depends(get_session)
):
    app = session.get(Application, id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    docs = session.exec(select(Document).where(Document.application_id == app.id)).all()
    doc_ids = [d.id for d in docs]

    fields = session.exec(
        select(ExtractedField).where(ExtractedField.document_id.in_(doc_ids))
    ).all() if doc_ids else []

    findings = session.exec(select(Finding).where(Finding.application_id == app.id)).all()
    
    verifications = session.exec(
        select(Verification).where(Verification.document_id.in_(doc_ids))
    ).all() if doc_ids else []

    risk_breakdown = []
    if app.risk_breakdown_json:
        try:
            risk_breakdown = json.loads(app.risk_breakdown_json)
        except Exception:
            risk_breakdown = []

    # Map parsed evidence in findings
    findings_list = []
    for f in findings:
        evidence = None
        if f.evidence_json:
            try:
                evidence = json.loads(f.evidence_json)
            except Exception:
                evidence = f.evidence_json
        findings_list.append({
            "id": f.id,
            "application_id": f.application_id,
            "document_id": f.document_id,
            "code": f.code,
            "severity": f.severity,
            "title": f.title,
            "message": f.message,
            "rule_id": f.rule_id,
            "evidence": evidence,
            "confidence": f.confidence,
            "status": f.status,
            "created_at": f.created_at
        })

    return {
        "id": app.id,
        "application_no": app.application_no,
        "institution_id": app.institution_id,
        "institution_name": app.institution_name,
        "aicte_id": app.aicte_id,
        "category": app.category,
        "academic_year": app.academic_year,
        "submitted_on": app.submitted_on,
        "status": app.status,
        "risk_band": app.risk_band,
        "risk_score": app.risk_score,
        "risk_breakdown": risk_breakdown,
        "folder": app.folder,
        "created_at": app.created_at,
        "documents": [d.model_dump() for d in docs],
        "fields": [f.model_dump() for f in fields],
        "findings": findings_list,
        "verifications": [v.model_dump() for v in verifications]
    }

@router.post("/{id}/run")
def run_application_pipeline(
    id: int,
    sync: bool = Query(default=False),
    session: Session = Depends(get_session)
):
    app = session.get(Application, id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    from app.pipeline.run import run_pipeline
    result = run_pipeline(app.id, session)
    return result

@router.get("/{id}/brief.pdf")
def get_application_inspection_brief(
    id: int,
    session: Session = Depends(get_session)
):
    app = session.get(Application, id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    from app.services.brief import generate_inspection_brief
    from fastapi.responses import Response
    pdf_bytes = generate_inspection_brief(app, session)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=brief_{app.institution_id}.pdf"
        }
    )


def _bg_run_pipeline(app_id: int):
    import time
    time.sleep(0.5)  # slight pause so client can observe processing status
    from app.db import engine
    with Session(engine) as bg_session:
        from app.pipeline.run import run_pipeline
        try:
            run_pipeline(app_id, bg_session)
        except Exception as e:
            print(f"Error running pipeline for {app_id}: {e}")
            app_rec = bg_session.get(Application, app_id)
            if app_rec:
                app_rec.status = "error"
                bg_session.add(app_rec)
                bg_session.commit()


@router.post("/upload-sample")
def upload_sample(
    payload: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session)
):
    folder_name = payload.get("folder", "INST04")
    from app.config import APPLICATIONS_DIR
    from app.seed import compute_sha256
    from pypdf import PdfReader
    import threading

    folder_path = APPLICATIONS_DIR / folder_name
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail=f"Sample folder {folder_name} not found")

    app_json_path = folder_path / "application.json"
    if not app_json_path.exists():
        raise HTTPException(status_code=400, detail="application.json not found in sample")

    with open(app_json_path, "r", encoding="utf-8") as f:
        app_data = json.load(f)

    institution_info = app_data.get("institution", {})

    # Check if app already exists in DB
    existing_app = session.exec(
        select(Application).where(Application.folder == folder_name)
    ).first()

    if existing_app:
        app_obj = existing_app
        # Clear existing relations
        docs = session.exec(select(Document).where(Document.application_id == app_obj.id)).all()
        doc_ids = [d.id for d in docs]
        if doc_ids:
            for f in session.exec(select(Finding).where(Finding.application_id == app_obj.id)).all():
                session.delete(f)
            for ef in session.exec(select(ExtractedField).where(ExtractedField.document_id.in_(doc_ids))).all():
                session.delete(ef)
            for v in session.exec(select(Verification).where(Verification.document_id.in_(doc_ids))).all():
                session.delete(v)
            for d in docs:
                session.delete(d)
        app_obj.status = "processing"
        app_obj.risk_score = 0.0
        app_obj.risk_band = None
        app_obj.risk_breakdown_json = None
        session.add(app_obj)
        session.commit()
        session.refresh(app_obj)
    else:
        app_obj = Application(
            application_no=app_data.get("application_id", f"APP-{folder_path.name}"),
            institution_id=institution_info.get("id", folder_path.name),
            institution_name=institution_info.get("name", "Unknown Institution"),
            aicte_id=institution_info.get("aicte_permanent_id", ""),
            category=app_data.get("category", "EoA"),
            academic_year=app_data.get("academic_year", "2027-28"),
            submitted_on=app_data.get("submitted_on", ""),
            status="processing",
            risk_score=0.0,
            risk_band=None,
            risk_breakdown_json=None,
            folder=folder_path.name
        )
        session.add(app_obj)
        session.commit()
        session.refresh(app_obj)

    # Re-insert documents
    documents_list = app_data.get("documents", [])
    for doc_item in documents_list:
        doc_type = doc_item.get("doc_type", "unknown")
        rel_file = doc_item.get("file", "")
        doc_file_path = folder_path / rel_file
        if not doc_file_path.exists():
            continue

        file_hash = compute_sha256(doc_file_path)
        scanned = False
        page_count = 1
        producer = None
        creation_date = None
        mod_date = None

        if doc_file_path.suffix.lower() == ".pdf":
            try:
                reader = PdfReader(str(doc_file_path))
                page_count = len(reader.pages)
                meta = reader.metadata
                if meta:
                    producer = meta.producer
                    creation_date = str(meta.creation_date) if meta.creation_date else None
                    mod_date = str(meta.modification_date) if meta.modification_date else None
                text_len = sum(len(p.extract_text() or "") for p in reader.pages)
                scanned = (text_len < 20)
            except Exception:
                pass

        doc_obj = Document(
            application_id=app_obj.id,
            doc_type=doc_type,
            file_path=str(doc_file_path).replace("\\", "/"),
            sha256=file_hash,
            scanned=scanned,
            page_count=page_count,
            producer=producer,
            creation_date=creation_date,
            mod_date=mod_date,
            ocr_confidence=None
        )
        session.add(doc_obj)

    photos_list = app_data.get("photos", [])
    for photo_item in photos_list:
        photo_type = photo_item.get("type", "unknown")
        doc_type = f"photo:{photo_type}"
        rel_file = photo_item.get("file", "")
        photo_file_path = folder_path / rel_file
        if not photo_file_path.exists():
            continue

        file_hash = compute_sha256(photo_file_path)
        doc_obj = Document(
            application_id=app_obj.id,
            doc_type=doc_type,
            file_path=str(photo_file_path).replace("\\", "/"),
            sha256=file_hash,
            scanned=False,
            page_count=1,
            producer=None,
            creation_date=None,
            mod_date=None,
            ocr_confidence=None
        )
        session.add(doc_obj)

    session.commit()

    # Log audit entry
    from app.services.audit import log_audit
    log_audit(
        session=session,
        actor="institution",
        action="upload_application_sample",
        entity_type="application",
        entity_id=app_obj.id,
        payload={"folder": folder_name, "application_no": app_obj.application_no}
    )

    # Start background processing thread
    threading.Thread(target=_bg_run_pipeline, args=(app_obj.id,), daemon=True).start()

    return {
        "id": app_obj.id,
        "application_no": app_obj.application_no,
        "status": app_obj.status
    }


@router.post("/upload")
async def upload_application(
    category: str = Form("EoA"),
    academic_year: str = Form("2027-28"),
    institution_name: str = Form(""),
    aicte_id: str = Form(""),
    declared_land_acres: Optional[float] = Form(None),
    declared_built_up_area_sqm: Optional[float] = Form(None),
    declared_faculty_count: Optional[int] = Form(None),
    files: List[UploadFile] = File(...),
    doc_types: List[str] = Form(...),
    session: Session = Depends(get_session)
):
    import time
    import threading
    from pathlib import Path
    from pypdf import PdfReader
    from app.config import STORAGE_DIR
    from app.seed import compute_sha256
    from app.services.audit import log_audit

    timestamp = int(time.time())
    app_no = f"APP-LIVE-{timestamp}"
    inst_id = f"INST-LIVE-{timestamp % 10000}"

    app_obj = Application(
        application_no=app_no,
        institution_id=inst_id,
        institution_name=institution_name or f"Institution {app_no}",
        aicte_id=aicte_id or f"1-LIVE-{timestamp % 100000}",
        category=category,
        academic_year=academic_year,
        submitted_on=datetime.utcnow().strftime("%Y-%m-%d"),
        status="processing",
        risk_score=0.0,
        risk_band=None,
        risk_breakdown_json=None,
        folder=f"live_{timestamp}"
    )
    session.add(app_obj)
    session.commit()
    session.refresh(app_obj)

    upload_dir = STORAGE_DIR / "uploads" / f"app_{app_obj.id}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Write synthetic application.json in upload_dir for pipeline compatibility
    declared_data = {
        "application_id": app_no,
        "institution": {
            "id": inst_id,
            "name": app_obj.institution_name,
            "aicte_permanent_id": app_obj.aicte_id
        },
        "category": category,
        "academic_year": academic_year,
        "declared": {
            "land_acres": declared_land_acres,
            "built_up_area_sqm": declared_built_up_area_sqm,
            "faculty_count": declared_faculty_count
        },
        "documents": [],
        "photos": []
    }

    for idx, file in enumerate(files):
        dtype = doc_types[idx] if idx < len(doc_types) else "unknown"
        safe_filename = Path(file.filename or f"doc_{idx}.pdf").name
        dest_path = upload_dir / safe_filename
        content = await file.read()
        dest_path.write_bytes(content)

        file_hash = compute_sha256(dest_path)
        scanned = False
        page_count = 1
        producer = None
        creation_date = None
        mod_date = None

        if dest_path.suffix.lower() == ".pdf":
            try:
                reader = PdfReader(str(dest_path))
                page_count = len(reader.pages)
                meta = reader.metadata
                if meta:
                    producer = meta.producer
                    creation_date = str(meta.creation_date) if meta.creation_date else None
                    mod_date = str(meta.modification_date) if meta.modification_date else None
                text_len = sum(len(p.extract_text() or "") for p in reader.pages)
                scanned = (text_len < 20)
            except Exception:
                pass

        doc_obj = Document(
            application_id=app_obj.id,
            doc_type=dtype,
            file_path=str(dest_path).replace("\\", "/"),
            sha256=file_hash,
            scanned=scanned,
            page_count=page_count,
            producer=producer,
            creation_date=creation_date,
            mod_date=mod_date,
            ocr_confidence=None
        )
        session.add(doc_obj)
        declared_data["documents"].append({
            "doc_type": dtype,
            "file": safe_filename
        })

    (upload_dir / "application.json").write_text(json.dumps(declared_data, indent=2), encoding="utf-8")
    session.commit()

    log_audit(
        session=session,
        actor="institution",
        action="upload_application",
        entity_type="application",
        entity_id=app_obj.id,
        payload={"application_no": app_obj.application_no, "files_count": len(files)}
    )

    threading.Thread(target=_bg_run_pipeline, args=(app_obj.id,), daemon=True).start()

    return {
        "id": app_obj.id,
        "application_no": app_obj.application_no,
        "status": app_obj.status
    }


