import io
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import cv2
import numpy as np
import pymupdf
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db import get_session
from app.models import ExtractedField, Document, Application, Finding
from app.pipeline.quality import compute_page_quality_metrics
from app.services.audit import log_audit
from app.config import DATA_DIR, APPLICATIONS_DIR

router = APIRouter(prefix="/api", tags=["quality"])

@router.post("/quality-check")
async def check_document_quality(file: UploadFile = File(...)):
    """
    Quality gate: runs quality check immediately on uploaded file.
    Reuses pipeline/quality.py compute_page_quality_metrics.
    Returns whether scan is clear and warning message with exact reason if not.
    """
    contents = await file.read()
    filename = file.filename or "uploaded_document.pdf"
    ext = Path(filename).suffix.lower()

    is_clear = True
    reasons: List[str] = []
    min_blur = 200.0
    min_dpi = 150.0

    try:
        if ext == ".pdf":
            with pymupdf.open(stream=contents, filetype="pdf") as doc:
                if len(doc) == 0:
                    return {
                        "is_clear": False,
                        "blur_variance": 0.0,
                        "effective_dpi": 0.0,
                        "reason": "PDF file is empty (0 pages)",
                        "warning": "Not clear — please re-scan",
                        "filename": filename
                    }
                page_metrics = []
                for pno in range(len(doc)):
                    metrics = compute_page_quality_metrics(doc[pno], doc)
                    page_metrics.append(metrics)

                min_blur = min(m["blur_variance"] for m in page_metrics)
                min_dpi = min(m["effective_dpi"] for m in page_metrics)
        else:
            # Image format (.jpg, .jpeg, .png)
            nparr = np.frombuffer(contents, np.uint8)
            gray = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            if gray is None:
                return {
                    "is_clear": False,
                    "blur_variance": 0.0,
                    "effective_dpi": 0.0,
                    "reason": "Unable to decode image file",
                    "warning": "Not clear — please re-scan",
                    "filename": filename
                }
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            min_blur = round(blur, 2)
            min_dpi = 150.0 if gray.shape[1] >= 800 else round(gray.shape[1] / 8.27, 1)

        # Thresholds from quality.py: blur variance < 100 or DPI < 150
        if min_blur < 100.0:
            is_clear = False
            reasons.append(f"Blur variance too low ({min_blur:.1f} < 100.0) indicating motion blur or defocus")
        if min_dpi < 150.0:
            is_clear = False
            reasons.append(f"Effective resolution below threshold ({min_dpi:.1f} DPI < 150.0 DPI)")

    except Exception as e:
        is_clear = False
        reasons.append(f"Scan analysis error: {str(e)}")

    reason_str = " & ".join(reasons) if reasons else None
    warning_msg = "Not clear — please re-scan" if not is_clear else None

    return {
        "is_clear": is_clear,
        "blur_variance": min_blur,
        "effective_dpi": min_dpi,
        "reason": reason_str,
        "warning": warning_msg,
        "filename": filename
    }


class FieldCorrectionRequest(BaseModel):
    value: str
    reviewer: Optional[str] = "Scrutiny Officer"
    comment: Optional[str] = None


@router.post("/fields/{id}/correct")
def correct_field_value(
    id: int,
    req: FieldCorrectionRequest,
    session: Session = Depends(get_session)
):
    """
    Saves a human-corrected value for any unreadable or low-confidence field,
    and writes an audit log entry.
    """
    field = session.get(ExtractedField, id)
    if not field:
        raise HTTPException(status_code=404, detail="Extracted field not found")

    old_value = field.value
    new_value = req.value.strip()

    field.value = new_value
    field.confidence = 1.0  # Officer verified

    doc = session.get(Document, field.document_id)
    app_id = doc.application_id if doc else None

    # If document had LOW_OCR_CONFIDENCE findings matching this field name, mark them accepted
    if doc:
        findings = session.exec(
            select(Finding).where(
                Finding.document_id == doc.id,
                Finding.code == "LOW_OCR_CONFIDENCE"
            )
        ).all()
        for f in findings:
            if field.name in f.title or field.name in f.message:
                f.status = "accepted"
                session.add(f)

    session.add(field)

    # Write immutable audit log row
    log_audit(
        session=session,
        actor=req.reviewer or "Scrutiny Officer",
        action="HUMAN_FIELD_CORRECTION",
        entity_type="ExtractedField",
        entity_id=str(field.id),
        payload={
            "field_name": field.name,
            "old_value": old_value,
            "new_value": new_value,
            "document_id": field.document_id,
            "application_id": app_id,
            "comment": req.comment or "Human officer manual correction"
        }
    )

    session.commit()
    session.refresh(field)

    return {
        "ok": True,
        "field": {
            "id": field.id,
            "name": field.name,
            "value": field.value,
            "confidence": field.confidence,
            "document_id": field.document_id,
            "page": field.page
        }
    }


@router.get("/samples")
def list_available_samples():
    """
    Returns available synthetic application packages from data/applications/
    for one-click sample loading in the upload page demo.
    """
    samples_dir = APPLICATIONS_DIR
    if not samples_dir.exists():
        samples_dir = DATA_DIR / "applications"

    samples: List[Dict[str, Any]] = []
    if not samples_dir.exists():
        return samples

    for folder_path in sorted(samples_dir.iterdir()):
        if folder_path.is_dir() and (folder_path / "application.json").exists():
            try:
                with open(folder_path / "application.json", "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Check available documents and photos
                doc_dir = folder_path / "documents"
                photo_dir = folder_path / "photos"
                docs_list = [p.name for p in doc_dir.glob("*.*")] if doc_dir.exists() else []
                photos_list = [p.name for p in photo_dir.glob("*.*")] if photo_dir.exists() else []

                inst = data.get("institution", {})
                raw_docs = data.get("documents", [])
                raw_photos = data.get("photos", [])

                combined_docs = []
                for d in raw_docs:
                    f_name = d.get("file", "").split("/")[-1] if "/" in d.get("file", "") else d.get("file", "")
                    combined_docs.append({
                        "doc_type": d.get("doc_type"),
                        "file": f_name,
                        "path": d.get("file", "")
                    })
                for p in raw_photos:
                    f_name = p.get("file", "").split("/")[-1] if "/" in p.get("file", "") else p.get("file", "")
                    combined_docs.append({
                        "doc_type": f"photo:{p.get('type')}",
                        "file": f_name,
                        "path": p.get("file", "")
                    })

                declared = data.get("declared", data.get("declared_values", {}))

                samples.append({
                    "folder": folder_path.name,
                    "institution_name": inst.get("name", folder_path.name),
                    "institution_id": inst.get("id", folder_path.name),
                    "aicte_id": inst.get("aicte_permanent_id") or inst.get("aicte_id", "N/A"),
                    "category": data.get("category", "EoA"),
                    "academic_year": data.get("academic_year", "2027-28"),
                    "documents_count": len(docs_list) + len(photos_list),
                    "programmes": data.get("programmes", []),
                    "declared": declared,
                    "declared_values": declared,
                    "institution": inst,
                    "documents": combined_docs,
                    "photos": raw_photos,
                    "documents_available": docs_list,
                    "photos_available": photos_list,
                })
            except Exception as e:
                print(f"Error reading sample {folder_path.name}: {e}")

    return samples
