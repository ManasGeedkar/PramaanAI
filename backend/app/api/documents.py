from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.db import get_session
from app.models import Document
from app.config import STORAGE_DIR

router = APIRouter(prefix="/api/documents", tags=["documents"])

@router.get("/{id}/file")
def get_document_file(
    id: int,
    session: Session = Depends(get_session)
):
    doc = session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File on disk not found")

    media_type = "application/pdf"
    if file_path.suffix.lower() in [".jpg", ".jpeg"]:
        media_type = "image/jpeg"
    elif file_path.suffix.lower() == ".png":
        media_type = "image/png"

    return FileResponse(path=str(file_path), media_type=media_type, filename=file_path.name)

import io
import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageChops

def generate_hot_ela_file(doc: Document) -> Path | None:
    file_path = Path(doc.file_path)
    if not file_path.exists() or file_path.suffix.lower() != ".pdf":
        return None

    ela_dir = STORAGE_DIR / "ela"
    ela_dir.mkdir(parents=True, exist_ok=True)
    hot_path = ela_dir / f"{doc.sha256}_hot.png"
    if hot_path.exists():
        return hot_path

    try:
        with pymupdf.open(str(file_path)) as pdoc:
            if len(pdoc) == 0:
                return None
            page = pdoc[0]
            imgs = page.get_images()
            orig_pil = None
            if imgs:
                try:
                    xref = imgs[0][0]
                    base_img = pdoc.extract_image(xref)
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

            p99 = np.percentile(diff_gray, 99)
            if p99 <= 0:
                p99 = 1.0

            diff_norm = np.clip((diff_gray / p99) * 255.0, 0, 255).astype(np.uint8)
            heatmap_hot = cv2.applyColorMap(diff_norm, cv2.COLORMAP_HOT)
            cv2.imwrite(str(hot_path), heatmap_hot)
            return hot_path
    except Exception as e:
        print(f"Error generating full-page HOT ELA for doc {doc.id}: {e}")
        return None


@router.get("/{id}/ela.png")
def get_document_ela_heatmap(
    id: int,
    session: Session = Depends(get_session)
):
    doc = session.get(Document, id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    hot_path = generate_hot_ela_file(doc)
    if hot_path and hot_path.exists():
        return FileResponse(path=str(hot_path), media_type="image/png", filename=f"ela_hot_{doc.sha256[:8]}.png")

    ela_path = STORAGE_DIR / "ela" / f"{doc.sha256}.png"
    if not ela_path.exists():
        ela_path = STORAGE_DIR / "ela" / f"{doc.id}.png"
    if not ela_path.exists():
        raise HTTPException(status_code=404, detail="ELA heatmap not found for this document")

    return FileResponse(path=str(ela_path), media_type="image/png", filename=f"ela_{doc.sha256[:8]}.png")
