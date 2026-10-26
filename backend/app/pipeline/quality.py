import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np
import pymupdf
from sqlmodel import Session, select

from app.models import Document, Finding, Verification, ExtractedField
from app.config import settings
from app.pipeline.cache import get_cached, set_cached

def compute_page_quality_metrics(page: pymupdf.Page, doc: pymupdf.Document) -> Dict[str, float]:
    """
    Computes Laplacian variance (blur), effective DPI, mean brightness and contrast for a page.
    """
    imgs = page.get_images()
    effective_dpi = 150.0
    gray_img = None

    if imgs:
        try:
            xref = imgs[0][0]
            base_img = doc.extract_image(xref)
            img_bytes = base_img["image"]
            nparr = np.frombuffer(img_bytes, np.uint8)
            gray_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
            h, w = gray_img.shape
            rect = page.rect
            dpi_x = w / (rect.width / 72.0) if rect.width > 0 else 150.0
            dpi_y = h / (rect.height / 72.0) if rect.height > 0 else 150.0
            effective_dpi = round(min(dpi_x, dpi_y), 1)
        except Exception:
            gray_img = None

    if gray_img is None:
        # Fallback to rendering page at 150 dpi
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        nparr = np.frombuffer(img_bytes, np.uint8)
        gray_img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
        effective_dpi = 150.0

    blur_variance = float(cv2.Laplacian(gray_img, cv2.CV_64F).var())
    mean_brightness = float(np.mean(gray_img))
    contrast = float(np.std(gray_img))

    return {
        "blur_variance": round(blur_variance, 2),
        "effective_dpi": round(effective_dpi, 1),
        "mean_brightness": round(mean_brightness, 2),
        "contrast": round(contrast, 2)
    }

def assess_document_quality(doc_record: Document, session: Session) -> Tuple[Optional[Dict[str, Any]], List[Finding]]:
    """
    Assesses quality for a scanned document.
    Stores quality_json on Document.
    Caches quality metrics by document sha256 in storage/cache/.
    If blur variance < 100 or DPI < 150, creates LOW_QUALITY_SCAN (info)
    and marks ELA as 'not assessable'.
    """
    file_path = Path(doc_record.file_path)
    if not file_path.exists() or file_path.suffix.lower() != ".pdf":
        return None, []

    if not doc_record.scanned:
        return None, []

    findings: List[Finding] = []

    # Check cache first
    cached_quality = get_cached(doc_record.sha256, "quality")
    if cached_quality is not None:
        quality_data = cached_quality
    else:
        with pymupdf.open(str(file_path)) as doc:
            if len(doc) == 0:
                return None, []

            page_metrics_list = []
            for pno in range(len(doc)):
                metrics = compute_page_quality_metrics(doc[pno], doc)
                page_metrics_list.append(metrics)

            min_blur = min(m["blur_variance"] for m in page_metrics_list)
            min_dpi = min(m["effective_dpi"] for m in page_metrics_list)
            avg_brightness = sum(m["mean_brightness"] for m in page_metrics_list) / len(page_metrics_list)
            avg_contrast = sum(m["contrast"] for m in page_metrics_list) / len(page_metrics_list)

            is_low_quality = (min_blur < 100.0 or min_dpi < 150.0)
            ela_assessable = not is_low_quality

            quality_data = {
                "blur_variance": round(min_blur, 2),
                "effective_dpi": round(min_dpi, 1),
                "mean_brightness": round(avg_brightness, 2),
                "contrast": round(avg_contrast, 2),
                "ela_assessable": ela_assessable,
                "pages": page_metrics_list
            }
            set_cached(doc_record.sha256, "quality", quality_data)

    min_blur = quality_data.get("blur_variance", 200.0)
    min_dpi = quality_data.get("effective_dpi", 200.0)
    ela_assessable = quality_data.get("ela_assessable", True)

    doc_record.quality_json = json.dumps(quality_data)
    if not ela_assessable:
        doc_record.ela_status = "not assessable"
        evidence = {
            "items": [{
                "document_id": doc_record.id,
                "doc_type": doc_record.doc_type,
                "page": 1,
                "field": "scan_quality",
                "value": f"blur={min_blur:.1f}, dpi={min_dpi:.1f}"
            }],
            "method": "laplacian_variance_dpi_check",
            "explanation": f"Document scan quality is low (blur variance: {min_blur:.1f} < 100 or DPI: {min_dpi:.1f} < 150). ELA tamper detection marked as not assessable."
        }
        finding = Finding(
            application_id=doc_record.application_id,
            document_id=doc_record.id,
            code="LOW_QUALITY_SCAN",
            severity="info",
            title="Low Quality Document Scan",
            message=f"Document scan quality is low (blur variance: {min_blur:.1f}, DPI: {min_dpi:.1f}). ELA not assessable.",
            confidence=round(min_blur, 2),
            evidence_json=json.dumps(evidence),
            status="open"
        )
        findings.append(finding)
    else:
        doc_record.ela_status = "assessable"

    session.add(doc_record)
    session.commit()
    session.refresh(doc_record)

    return quality_data, findings

def check_low_ocr_confidence_fields(
    doc_record: Document,
    fields: List[ExtractedField],
    session: Session
) -> List[Finding]:
    """
    If any key field's OCR confidence < 0.80, sets its value to 'null',
    creates LOW_OCR_CONFIDENCE (warning) naming the field,
    and sets document's verification to manual_review (unless QR or source lookup succeeds).
    """
    findings: List[Finding] = []
    doc_cfg = settings.doc_types.get(doc_record.doc_type, {})
    verify_cfg = doc_cfg.get("verify", {})
    key_field = verify_cfg.get("key_field") if isinstance(verify_cfg, dict) else None

    has_low_conf = False

    for field in fields:
        # Skip pseudo-fields like qr payloads and table rows
        if field.name in ["qr", "rows"]:
            continue

        if field.confidence is not None and field.confidence < 0.80:

            has_low_conf = True
            orig_val = field.value
            field.value = "null"
            session.add(field)

            evidence = {
                "items": [{
                    "document_id": doc_record.id,
                    "doc_type": doc_record.doc_type,
                    "page": field.page,
                    "field": field.name,
                    "value": orig_val
                }],
                "method": "ocr_confidence_check",
                "explanation": f"Field '{field.name}' on {doc_record.doc_type} had low OCR confidence ({field.confidence:.2f} < 0.80). Value suppressed for manual verification."
            }
            f = Finding(
                application_id=doc_record.application_id,
                document_id=doc_record.id,
                code="LOW_OCR_CONFIDENCE",
                severity="warning",
                title=f"Low OCR Confidence on {field.name}",
                message=f"Field '{field.name}' on {doc_record.doc_type} had low OCR confidence ({field.confidence:.2f} < 0.80). Value suppressed for manual verification.",
                confidence=field.confidence,
                evidence_json=json.dumps(evidence),
                status="open"
            )
            findings.append(f)

    # Check for missing/unreadable key fields on scanned documents
    if doc_record.scanned:
        expected_fields = list(doc_cfg.get("fields", {}).keys())
        extracted_names = {f.name for f in fields if f.value not in [None, "null", ""]}
        missing_fields = [fn for fn in expected_fields if fn not in extracted_names]
        if missing_fields:
            has_low_conf = True
            evidence = {
                "items": [{
                    "document_id": doc_record.id,
                    "doc_type": doc_record.doc_type,
                    "page": 1,
                    "field": "unreadable_fields",
                    "value": ", ".join(missing_fields)
                }],
                "method": "unreadable_scan_check",
                "explanation": f"Could not read: {', '.join(missing_fields)} on {doc_record.doc_type}"
            }
            f_missing = Finding(
                application_id=doc_record.application_id,
                document_id=doc_record.id,
                code="LOW_OCR_CONFIDENCE",
                severity="warning",
                title=f"Unreadable Fields on {doc_record.doc_type}",
                message=f"Could not read: {', '.join(missing_fields)}",
                confidence=0.0,
                evidence_json=json.dumps(evidence),
                status="open"
            )
            findings.append(f_missing)


    if has_low_conf:
        # Check if verification already exists or create pending manual_review
        existing_verif = session.exec(
            select(Verification).where(Verification.document_id == doc_record.id)
        ).first()

        # If not verified yet or verified with failure, mark manual_review
        if not existing_verif or existing_verif.status not in ["verified"]:
            if not existing_verif:
                existing_verif = Verification(
                    document_id=doc_record.id,
                    source="ocr_quality_check",
                    reference=doc_record.doc_type,
                    status="manual_review",
                    details_json=json.dumps({"reason": "Low OCR confidence on key field(s)"})
                )
            else:
                existing_verif.status = "manual_review"
                existing_verif.details_json = json.dumps({"reason": "Low OCR confidence on key field(s)"})
            session.add(existing_verif)

    session.commit()
    return findings
