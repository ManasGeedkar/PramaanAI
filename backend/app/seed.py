import os
import json
import hashlib
from pathlib import Path
from pypdf import PdfReader
from sqlmodel import Session, select
from app.config import APPLICATIONS_DIR, settings
from app.models import Application, Document, RuleSet
from app.services.audit import log_audit

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def seed_database_if_empty(session: Session, force: bool = False):
    if not force:
        existing = session.exec(select(Application)).first()
        if existing is not None:
            return

    if not APPLICATIONS_DIR.exists():
        return

    app_folders = sorted([p for p in APPLICATIONS_DIR.iterdir() if p.is_dir() and p.name.startswith("INST")])

    # When DEMO_LIVE_UPLOAD=1, do not seed INST04 at all
    if os.environ.get("DEMO_LIVE_UPLOAD") == "1":
        app_folders = [p for p in app_folders if p.name != "INST04"]

    for folder_path in app_folders:
        app_json_path = folder_path / "application.json"
        if not app_json_path.exists():
            continue

        with open(app_json_path, "r", encoding="utf-8") as f:
            app_data = json.load(f)

        institution_info = app_data.get("institution", {})
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

        log_audit(
            session=session,
            actor="system",
            action="seed_application",
            entity_type="application",
            entity_id=app_obj.id,
            payload={
                "application_no": app_obj.application_no,
                "institution_id": app_obj.institution_id,
                "folder": app_obj.folder
            }
        )

        # 1. Documents
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
                    
                    # Detect scanned doc if extracted text layer is empty
                    text_len = sum(len(p.extract_text() or "") for p in reader.pages)
                    scanned = (text_len < 20)
                except Exception as e:
                    print(f"Error reading PDF metadata for {doc_file_path}: {e}")

            # Store file_path as relative to project data or normalized string
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

        # 2. Photos
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

    # Seed RuleSet from rules.yaml if not present
    existing_rule_set = session.exec(select(RuleSet)).first()
    if existing_rule_set is None:
        rules_yaml_text = settings.raw_rules_yaml()
        version = settings.rules.get("version", "2027-28.v1") if settings.rules else "2027-28.v1"
        rule_set = RuleSet(
            version=version,
            yaml_text=rules_yaml_text,
            active=True
        )
        session.add(rule_set)
        session.commit()

