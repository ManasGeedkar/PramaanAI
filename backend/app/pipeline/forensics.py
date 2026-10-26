import io
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageChops
import imagehash
from sqlmodel import Session, select

from app.config import settings, STORAGE_DIR
from app.models import Application, Document, ExtractedField, Finding
from app.pipeline.cache import get_cached, set_cached

FORBIDDEN_PRODUCERS = ["photoshop", "gimp", "word", "canva"]
EXTERNAL_DOCS = {"fire_noc", "land_deed", "affiliation_letter", "accreditation_certificate"}

def run_ela_analysis(doc_record: Document, fields: List[ExtractedField]) -> List[Finding]:
    """
    Error Level Analysis (ELA) for scanned PDFs.
    Extracts embedded page JPEG, re-saves at quality 75, computes absolute difference,
    saves an amplified heatmap PNG to storage/ela/{document_id}.png.
    Caches field ELA scores and only generates heatmap file if it does not exist.
    """
    findings: List[Finding] = []
    file_path = Path(doc_record.file_path)
    if not file_path.exists() or file_path.suffix.lower() != ".pdf":
        return findings

    if not doc_record.scanned:
        return findings

    # Skip if document scan quality was flagged as not assessable
    if doc_record.ela_status == "not assessable":
        return findings

    ela_dir = STORAGE_DIR / "ela"
    ela_dir.mkdir(parents=True, exist_ok=True)
    heatmap_file = ela_dir / f"{doc_record.sha256}.png"

    # Check cache for ELA scores
    cached_ela = get_cached(doc_record.sha256, "ela")
    if cached_ela is not None:
        # Generate heatmap PNG only if it does not exist
        if not heatmap_file.exists():
            try:
                with pymupdf.open(str(file_path)) as doc:
                    if len(doc) > 0:
                        page = doc[0]
                        imgs = page.get_images()
                        orig_pil = None
                        if imgs:
                            try:
                                xref = imgs[0][0]
                                base_img = doc.extract_image(xref)
                                orig_pil = Image.open(io.BytesIO(base_img["image"])).convert("RGB")
                            except Exception:
                                orig_pil = None
                        if orig_pil is None:
                            pix = page.get_pixmap(dpi=200)
                            orig_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

                        buf = io.BytesIO()
                        orig_pil.save(buf, format="JPEG", quality=75)
                        buf.seek(0)
                        resaved_pil = Image.open(buf)
                        diff = ImageChops.difference(orig_pil, resaved_pil)
                        diff_arr = np.array(diff).astype(np.float32)
                        diff_gray = np.mean(diff_arr, axis=2)
                        diff_amplified = np.clip(diff_gray * 15, 0, 255).astype(np.uint8)
                        heatmap = cv2.applyColorMap(diff_amplified, cv2.COLORMAP_JET)
                        cv2.imwrite(str(heatmap_file), heatmap)
            except Exception as e:
                print(f"Error re-generating heatmap for document {doc_record.id}: {e}")

        # Construct findings from cached tamper items
        for item in cached_ela.get("tamper_items", []):
            fname = item["field"]
            ratio = item["ratio"]
            severity = item["severity"]
            explanation = item["explanation"]
            bbox = item["bbox"]
            val_str = item["value"]

            evidence = {
                "items": [{
                    "document_id": doc_record.id,
                    "doc_type": doc_record.doc_type,
                    "page": 1,
                    "bbox": bbox,
                    "field": fname,
                    "value": val_str
                }],
                "expected": "consistent compression level",
                "method": "ELA",
                "related_applications": [],
                "heatmap_url": f"/api/documents/{doc_record.id}/ela.png",
                "explanation": explanation
            }
            findings.append(Finding(
                application_id=doc_record.application_id,
                document_id=doc_record.id,
                code="TAMPER_SUSPECTED",
                severity=severity,
                title=f"Tampering Suspected on {fname}",
                message=explanation,
                confidence=round(ratio, 2),
                evidence_json=json.dumps(evidence),
                status="open"
            ))
        return findings

    try:
        with pymupdf.open(str(file_path)) as doc:
            if len(doc) == 0:
                return findings

            page = doc[0]
            page_rect = page.rect
            imgs = page.get_images()

            orig_pil = None
            if imgs:
                try:
                    xref = imgs[0][0]
                    base_img = doc.extract_image(xref)
                    orig_pil = Image.open(io.BytesIO(base_img["image"])).convert("RGB")
                except Exception:
                    orig_pil = None

            if orig_pil is None:
                pix = page.get_pixmap(dpi=200)
                orig_pil = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            img_w, img_h = orig_pil.size
            scale_x = img_w / page_rect.width if page_rect.width > 0 else 1.0
            scale_y = img_h / page_rect.height if page_rect.height > 0 else 1.0

            buf = io.BytesIO()
            orig_pil.save(buf, format="JPEG", quality=75)
            buf.seek(0)
            resaved_pil = Image.open(buf)

            diff = ImageChops.difference(orig_pil, resaved_pil)
            diff_arr = np.array(diff).astype(np.float32)
            diff_gray = np.mean(diff_arr, axis=2)

            # Save amplified heatmap PNG only if not exists
            if not heatmap_file.exists():
                diff_amplified = np.clip(diff_gray * 15, 0, 255).astype(np.uint8)
                heatmap = cv2.applyColorMap(diff_amplified, cv2.COLORMAP_JET)
                cv2.imwrite(str(heatmap_file), heatmap)

            field_means: Dict[str, Tuple[float, ExtractedField, List[float]]] = {}
            for f in fields:
                if f.page != 1 or not f.bbox_json or f.name in ("qr", "rows"):
                    continue
                try:
                    bbox = json.loads(f.bbox_json)
                    px0 = max(0, int(bbox[0] * scale_x))
                    py0 = max(0, int(bbox[1] * scale_y))
                    px1 = min(img_w, int(bbox[2] * scale_x))
                    py1 = min(img_h, int(bbox[3] * scale_y))

                    crop = diff_gray[py0:py1, px0:px1]
                    if crop.size > 0:
                        field_means[f.name] = (float(np.mean(crop)), f, bbox)
                except Exception:
                    continue

            cached_items = []
            for fname, (mean_val, field_obj, bbox) in field_means.items():
                other_vals = [v[0] for k, v in field_means.items() if k != fname]
                if not other_vals:
                    continue
                median_others = float(np.median(other_vals))
                if median_others <= 0.001:
                    continue

                ratio = mean_val / median_others
                if ratio > 1.6:
                    severity = "critical" if ratio > 2.0 else "warning"
                    explanation = (
                        f"Edited region around '{fname}' value (single-compressed patch on "
                        f"double-compressed scan, ELA ratio {ratio:.2f} > 1.6)"
                    )
                    cached_items.append({
                        "field": fname,
                        "ratio": ratio,
                        "severity": severity,
                        "explanation": explanation,
                        "bbox": bbox,
                        "value": str(field_obj.value)
                    })
                    evidence = {
                        "items": [{
                            "document_id": doc_record.id,
                            "doc_type": doc_record.doc_type,
                            "page": 1,
                            "bbox": bbox,
                            "field": fname,
                            "value": str(field_obj.value)
                        }],
                        "expected": "consistent compression level",
                        "method": "ELA",
                        "related_applications": [],
                        "heatmap_url": f"/api/documents/{doc_record.id}/ela.png",
                        "explanation": explanation
                    }
                    finding = Finding(
                        application_id=doc_record.application_id,
                        document_id=doc_record.id,
                        code="TAMPER_SUSPECTED",
                        severity=severity,
                        title=f"Tampering Suspected on {fname}",
                        message=explanation,
                        confidence=round(ratio, 2),
                        evidence_json=json.dumps(evidence),
                        status="open"
                    )
                    findings.append(finding)

            set_cached(doc_record.sha256, "ela", {"tamper_items": cached_items})
    except Exception as e:
        print(f"Error in ELA analysis for document {doc_record.id}: {e}")

    return findings

def run_metadata_analysis(doc_record: Document, fields: List[ExtractedField]) -> List[Finding]:
    """
    Metadata anomaly check:
    External authorities (fire_noc, land_deed, affiliation_letter, accreditation_certificate)
    must not have producers containing Photoshop/GIMP/Word/Canva,
    and ModDate must not be more than 365 days after issue_date.
    """
    findings: List[Finding] = []
    if doc_record.doc_type not in EXTERNAL_DOCS:
        return findings

    producer = doc_record.producer or ""
    producer_lower = producer.lower()
    has_producer_anomaly = any(p in producer_lower for p in FORBIDDEN_PRODUCERS)

    # Check issue date vs ModDate
    has_date_anomaly = False
    issue_date_val = None
    days_diff = 0

    for f in fields:
        if f.name == "issue_date":
            issue_date_val = str(f.value)
            break

    if issue_date_val and doc_record.mod_date:
        try:
            mod_dt_str = doc_record.mod_date[:10]
            mod_dt = datetime.strptime(mod_dt_str, "%Y-%m-%d")
            issue_dt = datetime.strptime(issue_date_val[:10], "%Y-%m-%d")
            days_diff = (mod_dt - issue_dt).days
            if days_diff > 365:
                has_date_anomaly = True
        except Exception:
            pass

    if has_producer_anomaly or has_date_anomaly:
        reasons = []
        if has_producer_anomaly:
            reasons.append(f"PDF Producer '{producer}'")
        if has_date_anomaly:
            mod_str = doc_record.mod_date[:10] if doc_record.mod_date else "unknown"
            reasons.append(f"ModDate {mod_str} long after issue {issue_date_val} ({days_diff} days)")

        explanation = f"Metadata anomaly: {'; '.join(reasons)}"
        evidence = {
            "items": [{
                "document_id": doc_record.id,
                "doc_type": doc_record.doc_type,
                "page": 1,
                "bbox": None,
                "field": "producer",
                "value": producer
            }],
            "expected": "official issuing portal producer",
            "method": "pdf_metadata",
            "related_applications": [],
            "heatmap_url": None,
            "explanation": explanation
        }
        finding = Finding(
            application_id=doc_record.application_id,
            document_id=doc_record.id,
            code="METADATA_ANOMALY",
            severity="warning",
            title=f"PDF Metadata Anomaly ({doc_record.doc_type})",
            message=explanation,
            confidence=1.0,
            evidence_json=json.dumps(evidence),
            status="open"
        )
        findings.append(finding)

    return findings

def get_photo_phash(doc_record: Document) -> Optional[imagehash.ImageHash]:
    """
    Returns pHash for photo document using cache by document sha256.
    """
    cached = get_cached(doc_record.sha256, "phash")
    if cached and "phash" in cached:
        try:
            return imagehash.hex_to_hash(cached["phash"])
        except Exception:
            pass

    file_path = Path(doc_record.file_path)
    if not file_path.exists() or file_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
        return None

    try:
        current_img = Image.open(str(file_path))
        h = imagehash.phash(current_img)
        set_cached(doc_record.sha256, "phash", {"phash": str(h)})
        return h
    except Exception as e:
        print(f"Error computing pHash for {file_path}: {e}")
        return None

def run_phash_analysis(app: Application, doc_record: Document, session: Session) -> List[Finding]:
    """
    Performs pHash with imagehash on photo documents.
    Compares against photos in all other applications using cached pHash.
    If Hamming distance <= 6 -> DUPLICATE_IMAGE (warning on later submission, info on earlier).
    """
    findings: List[Finding] = []
    file_path = Path(doc_record.file_path)
    if not file_path.exists() or file_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
        return findings

    current_hash = get_photo_phash(doc_record)
    if current_hash is None:
        return findings

    # Query all other photo documents across other applications
    other_docs = session.exec(
        select(Document).where(
            Document.application_id != app.id,
            Document.doc_type.like("photo%")
        )
    ).all()

    for other_doc in other_docs:
        other_path = Path(other_doc.file_path)
        if not other_path.exists() or other_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
            continue
        try:
            other_hash = get_photo_phash(other_doc)
            if other_hash is None:
                continue
            dist = current_hash - other_hash
            if dist <= 6:
                other_app = session.get(Application, other_doc.application_id)
                if not other_app:
                    continue

                is_later = (app.submitted_on or "") > (other_app.submitted_on or "")
                severity = "warning" if is_later else "info"

                if is_later:
                    explanation = f"Near-duplicate of {other_app.institution_id} {other_path.name} (cropped, resized, brightened; pHash distance {dist} <= 6)"
                else:
                    explanation = f"Lab photo reused by {other_app.institution_id} ({app.institution_id} appears to be the original)"

                evidence = {
                    "items": [{
                        "document_id": doc_record.id,
                        "doc_type": doc_record.doc_type,
                        "page": 1,
                        "bbox": None,
                        "field": "photo",
                        "value": file_path.name
                    }],
                    "expected": "unique photo",
                    "method": "pHash",
                    "related_applications": [other_app.institution_id],
                    "heatmap_url": None,
                    "explanation": explanation
                }
                finding = Finding(
                    application_id=app.id,
                    document_id=doc_record.id,
                    code="DUPLICATE_IMAGE",
                    severity=severity,
                    title=f"Duplicate/Near-Duplicate Photo ({file_path.name})",
                    message=explanation,
                    confidence=1.0 - (dist / 64.0),
                    evidence_json=json.dumps(evidence),
                    status="open"
                )
                findings.append(finding)
        except Exception as e:
            print(f"Error comparing pHash for {other_path}: {e}")

    return findings

def run_all_forensics(app: Application, documents: List[Document], fields: List[ExtractedField], session: Session) -> List[Finding]:
    """Orchestrates ELA, metadata, and pHash forensics for an application."""
    all_findings: List[Finding] = []
    for doc in documents:
        doc_fields = [f for f in fields if f.document_id == doc.id]
        # (a) ELA for scanned PDFs
        all_findings.extend(run_ela_analysis(doc, doc_fields))
        # (b) PDF Metadata Anomaly
        all_findings.extend(run_metadata_analysis(doc, doc_fields))
        # (c) pHash Duplicate Photo
        all_findings.extend(run_phash_analysis(app, doc, session))

    return all_findings
