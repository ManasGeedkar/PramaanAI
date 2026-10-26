import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import pymupdf
from sqlmodel import Session

from app.config import settings, STORAGE_DIR
from app.models import Document, ExtractedField
from app.pipeline.classify import classify_document
from app.pipeline.qr import detect_and_decode_qr
from app.pipeline.cache import get_cached, set_cached

# Initialize RapidOCR with pytesseract fallback
try:
    from rapidocr_onnxruntime import RapidOCR
    rapid_ocr = RapidOCR()
except Exception:
    rapid_ocr = None

def clean_label(text: str) -> str:
    """Normalize label text for robust anchor matching against OCR noise."""
    t = re.sub(r"[^a-zA-Z0-9]", "", text).lower()
    # Normalize OCR-prone character confusions (e.g., 'l' in 'Date of lssue' vs 'Issue')
    t = t.replace("l", "i").replace("0", "o")
    return t

def parse_date(val: str) -> str:
    """Parse dd-mm-yyyy or dd/mm/yyyy to ISO yyyy-mm-dd."""
    if not val:
        return ""
    val = val.strip()
    m = re.search(r"(\d{2})[-/](\d{2})[-/](\d{4})", val)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return val

def parse_number(val: Any, regex: Optional[str] = None) -> Union[int, float, str]:
    """Parse number removing commas, units, and extra whitespace."""
    if isinstance(val, (int, float)):
        return val
    val_str = str(val)
    if regex:
        m = re.search(regex, val_str, re.IGNORECASE)
        if m:
            val_str = m.group(1) if m.groups() else m.group(0)

    val_str = val_str.replace(",", "").strip()
    m = re.search(r"[-+]?\d*\.?\d+", val_str)
    if m:
        s = m.group(0)
        return float(s) if "." in s else int(s)
    return val_str

def extract_fields_from_tokens(
    tokens: List[Tuple[float, float, float, float, str, int, int, int]],
    fields_cfg: Dict[str, Any],
    page_num: int = 1
) -> Dict[str, Dict[str, Any]]:
    """
    Extracts fields by finding label anchor on the page and taking words to the right.
    tokens: list of (x0, y0, x1, y1, text, block, line, word)
    """
    results: Dict[str, Dict[str, Any]] = {}

    for fname, fcfg in fields_cfg.items():
        lbl = fcfg.get("label", "")
        clean_lbl = clean_label(lbl)
        if not clean_lbl:
            continue

        has_colon = ":" in lbl
        best_match = None
        # First pass: try matching with colon requirement if label specifies colon
        for i in range(len(tokens)):
            if tokens[i][0] > 280:
                continue
            curr_str = ""
            matched = []
            for j in range(i, min(i + 10, len(tokens))):
                curr_str += clean_label(tokens[j][4])
                matched.append(tokens[j])
                if curr_str == clean_lbl:
                    if has_colon and not any(":" in t[4] for t in matched):
                        break
                    best_match = matched
                    break
                if len(curr_str) > len(clean_lbl):
                    break
            if best_match:
                break

        # Second pass: fallback without colon if not found
        if not best_match:
            for i in range(len(tokens)):
                if tokens[i][0] > 280:
                    continue
                curr_str = ""
                matched = []
                for j in range(i, min(i + 10, len(tokens))):
                    curr_str += clean_label(tokens[j][4])
                    matched.append(tokens[j])
                    if curr_str == clean_lbl:
                        best_match = matched
                        break
                    if len(curr_str) > len(clean_lbl):
                        break
                if best_match:
                    break


        if best_match:
            lbl_x1 = max(w[2] for w in best_match)
            lbl_ymid = (min(w[1] for w in best_match) + max(w[3] for w in best_match)) / 2.0
            line_h = max(w[3] for w in best_match) - min(w[1] for w in best_match)

            val_words = [
                w for w in tokens
                if w not in best_match
                and w[0] >= lbl_x1 - 4.0
                and abs((w[1] + w[3]) / 2.0 - lbl_ymid) <= max(6.5, line_h * 0.8)
            ]
            val_words.sort(key=lambda w: w[0])

            if val_words:
                raw_text = " ".join(w[4] for w in val_words).strip()
                ftype = fcfg.get("type")
                regex = fcfg.get("regex")

                final_val = raw_text
                if regex:
                    m = re.search(regex, raw_text, re.IGNORECASE)
                    if m:
                        if ftype == "number":
                            final_val = parse_number(m.group(1) if m.groups() else m.group(0))
                        else:
                            final_val = m.group(0)

                if ftype == "date":
                    final_val = parse_date(str(final_val))
                elif ftype == "number" and not isinstance(final_val, (int, float)):
                    final_val = parse_number(final_val, regex)
                elif ftype is None and isinstance(final_val, str):
                    # Spacing cleanups for survey numbers like 'Khasra No.720/7' -> 'Khasra No. 720/7'
                    final_val = re.sub(r"No\.(\d)", r"No. \1", final_val)
                    final_val = final_val.strip()

                field_conf = round(sum(w[8] for w in val_words if len(w) > 8) / len(val_words), 2) if any(len(w) > 8 for w in val_words) else 1.0

                bbox = [
                    round(min(w[0] for w in val_words), 1),
                    round(min(w[1] for w in val_words), 1),
                    round(max(w[2] for w in val_words), 1),
                    round(max(w[3] for w in val_words), 1)
                ]
                results[fname] = {
                    "value": str(final_val),
                    "page": page_num,
                    "bbox": bbox,
                    "confidence": field_conf
                }


    return results

def extract_faculty_rows(doc: pymupdf.Document, regex_pattern: str) -> List[Dict[str, Any]]:
    """Parse faculty rows for faculty_list document across pages."""
    pattern = re.compile(regex_pattern)
    parsed_rows: List[Dict[str, Any]] = []

    for pno in range(len(doc)):
        page = doc[pno]
        words = page.get_text("words")
        if not words:
            continue

        # Group words by vertical line position (tolerance 3.5 points)
        line_groups: Dict[float, List[Any]] = {}
        for w in words:
            found_y = None
            for y in line_groups.keys():
                if abs(w[1] - y) <= 3.5:
                    found_y = y
                    break
            if found_y is None:
                found_y = w[1]
                line_groups[found_y] = []
            line_groups[found_y].append(w)

        for y in sorted(line_groups.keys()):
            row_words = sorted(line_groups[y], key=lambda w: w[0])
            line_str = " ".join(w[4] for w in row_words)
            m = pattern.search(line_str)
            if m:
                faculty_id = m.group(1)
                name = m.group(2).strip()
                dob = parse_date(m.group(3))
                bbox = [
                    round(min(w[0] for w in row_words), 1),
                    round(min(w[1] for w in row_words), 1),
                    round(max(w[2] for w in row_words), 1),
                    round(max(w[3] for w in row_words), 1)
                ]
                parsed_rows.append({
                    "faculty_id": faculty_id,
                    "name": name,
                    "dob": dob,
                    "page": pno + 1,
                    "bbox": bbox
                })

    return parsed_rows

def extract_document(doc_record: Document, session: Session) -> List[ExtractedField]:
    """Extract all fields, QR payloads, and metadata from a document."""
    file_path = Path(doc_record.file_path)
    if not file_path.exists():
        return []

    # If it is a photo, return empty list (photos handled in forensics)
    if file_path.suffix.lower() not in [".pdf"]:
        return []

    extracted_fields: List[ExtractedField] = []

    with pymupdf.open(str(file_path)) as doc:
        doc_record.page_count = len(doc)
        total_ocr_scores = []

        ocr_cache_file = STORAGE_DIR / "ocr_cache" / f"{doc_record.sha256}.json"
        (STORAGE_DIR / "ocr_cache").mkdir(parents=True, exist_ok=True)

        cached_ocr_data = None
        if ocr_cache_file.exists():
            try:
                with open(ocr_cache_file, "r", encoding="utf-8") as f:
                    cached_ocr_data = json.load(f)
            except Exception:
                cached_ocr_data = None

        all_text = ""
        page_tokens_map = {}
        new_ocr_cache = {"pages": {}, "scores": []}

        for pno in range(len(doc)):
            page = doc[pno]
            words = page.get_text("words")

            if len(words) >= 5:
                # Text layer present
                all_text += " " + " ".join(w[4] for w in words)
                page_tokens_map[pno + 1] = [(w[0], w[1], w[2], w[3], w[4], w[5], w[6], w[7], 1.0) for w in words]
            else:
                p_key = str(pno + 1)
                tokens = []
                if cached_ocr_data and p_key in cached_ocr_data.get("pages", {}):
                    # Load from cache
                    raw_tokens = cached_ocr_data["pages"][p_key]
                    tokens = [tuple(t) for t in raw_tokens]
                    page_scores = cached_ocr_data.get("scores", [])
                    total_ocr_scores.extend(page_scores)
                else:
                    # Scanned page - perform OCR at 200 dpi
                    pix = page.get_pixmap(dpi=200)
                    img_bytes = pix.tobytes("png")
                    page_scores = []
                    if rapid_ocr:
                        ocr_res, _ = rapid_ocr(img_bytes)
                        if ocr_res:
                            for item in ocr_res:
                                box, text, score = item
                                page_scores.append(float(score))
                                total_ocr_scores.append(float(score))
                                bx0 = min(p[0] for p in box) * 72.0 / 200.0
                                by0 = min(p[1] for p in box) * 72.0 / 200.0
                                bx1 = max(p[0] for p in box) * 72.0 / 200.0
                                by1 = max(p[1] for p in box) * 72.0 / 200.0
                                tokens.append((bx0, by0, bx1, by1, text.strip(), 0, 0, 0, float(score)))
                    new_ocr_cache["pages"][p_key] = tokens
                    new_ocr_cache["scores"].extend(page_scores)

                all_text += " " + " ".join(t[4] for t in tokens)
                page_tokens_map[pno + 1] = tokens

        # Write to cache if newly performed OCR
        if not cached_ocr_data and new_ocr_cache["pages"]:
            try:
                with open(ocr_cache_file, "w", encoding="utf-8") as f:
                    json.dump(new_ocr_cache, f)
            except Exception:
                pass



        # Update scanned status and OCR confidence
        if total_ocr_scores:
            doc_record.scanned = True
            doc_record.ocr_confidence = round(sum(total_ocr_scores) / len(total_ocr_scores), 3)
        else:
            doc_record.scanned = False
            doc_record.ocr_confidence = 1.0

        # Classify document type if unknown or needs confirmation
        classified_type = classify_document(all_text, filename=doc_record.file_path, default_type=doc_record.doc_type)
        if classified_type and classified_type != "unknown":
            doc_record.doc_type = classified_type

        session.add(doc_record)
        session.commit()
        session.refresh(doc_record)

        # Extract fields based on doc_types.yaml configuration
        doc_cfg = settings.doc_types.get(doc_record.doc_type, {})
        fields_cfg = doc_cfg.get("fields", {})

        # Extract per page
        for pno in range(1, len(doc) + 1):
            tokens = page_tokens_map.get(pno, [])
            if not tokens:
                continue
            page_extracted = extract_fields_from_tokens(tokens, fields_cfg, page_num=pno)
            for fname, item in page_extracted.items():
                # Avoid overwriting if earlier page already found it
                if not any(f.name == fname for f in extracted_fields):
                    ef = ExtractedField(
                        document_id=doc_record.id,
                        name=fname,
                        value=item["value"],
                        page=item["page"],
                        bbox_json=json.dumps(item["bbox"]),
                        confidence=item["confidence"]
                    )
                    extracted_fields.append(ef)

        # Faculty list rows extraction
        if doc_record.doc_type == "faculty_list" and "rows" in doc_cfg:
            rows_regex = doc_cfg["rows"].get("regex")
            if rows_regex:
                faculty_rows = extract_faculty_rows(doc, rows_regex)
                ef_rows = ExtractedField(
                    document_id=doc_record.id,
                    name="rows",
                    value=json.dumps(faculty_rows),
                    page=1,
                    bbox_json=None,
                    confidence=1.0
                )
                extracted_fields.append(ef_rows)

        # QR code detection for document types requiring QR
        verify_cfg = doc_cfg.get("verify")
        expects_qr = isinstance(verify_cfg, dict) and verify_cfg.get("qr", False)

        if expects_qr:
            cached_qr = get_cached(doc_record.sha256, "qr")
            if cached_qr is not None:
                qr_dict = cached_qr.get("qr_dict")
                qr_bbox = cached_qr.get("qr_bbox")
                qr_page = cached_qr.get("qr_page", 1)
            else:
                qr_dict, qr_bbox, qr_page = detect_and_decode_qr(doc)
                set_cached(doc_record.sha256, "qr", {
                    "qr_dict": qr_dict,
                    "qr_bbox": qr_bbox,
                    "qr_page": qr_page
                })

            if qr_dict is not None:
                ef_qr = ExtractedField(
                    document_id=doc_record.id,
                    name="qr",
                    value=json.dumps(qr_dict),
                    page=qr_page,
                    bbox_json=json.dumps(qr_bbox) if qr_bbox else None,
                    confidence=1.0
                )
                extracted_fields.append(ef_qr)
            else:
                # Store QR not found as JSON null / None
                ef_qr = ExtractedField(
                    document_id=doc_record.id,
                    name="qr",
                    value=None,
                    page=1,
                    bbox_json=None,
                    confidence=0.0
                )
                extracted_fields.append(ef_qr)

    return extracted_fields

