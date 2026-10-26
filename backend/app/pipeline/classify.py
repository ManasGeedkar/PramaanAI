import re
from typing import Optional
from app.config import settings

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-zA-Z0-9\s]", " ", text)).strip().upper()

def classify_document(text: str, filename: str = "", default_type: Optional[str] = None) -> str:
    norm_text = normalize_text(text)
    doc_types_cfg = settings.doc_types

    # Check against classify_keywords in doc_types.yaml
    for doc_type, cfg in doc_types_cfg.items():
        if not isinstance(cfg, dict):
            continue
        keywords = cfg.get("classify_keywords", [])
        for kw in keywords:
            norm_kw = normalize_text(kw)
            if norm_kw and norm_kw in norm_text:
                return doc_type

    # Fallback checking filename if text is inconclusive
    fn_lower = filename.lower()
    for doc_type in doc_types_cfg.keys():
        if doc_type in fn_lower:
            return doc_type

    if "fire" in fn_lower or "noc" in fn_lower:
        return "fire_noc"
    if "land" in fn_lower or "deed" in fn_lower:
        return "land_deed"
    if "affil" in fn_lower:
        return "affiliation_letter"
    if "accred" in fn_lower:
        return "accreditation_certificate"
    if "faculty" in fn_lower:
        return "faculty_list"
    if "affidavit" in fn_lower:
        return "affidavit"

    return default_type or "unknown"
