import json
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from app.config import MOCK_SOURCES_DIR

router = APIRouter(prefix="/mock", tags=["mock"])

def load_mock_json(filename: str) -> Dict[str, Any]:
    file_path = MOCK_SOURCES_DIR / filename
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

# 1. Fire NOC Registry
@router.get("/fire-noc")
@router.get("/fire-noc/{noc_no:path}")
def get_fire_noc(noc_no: Optional[str] = None, no: Optional[str] = Query(default=None)):
    lookup_key = noc_no or no
    if not lookup_key:
        raise HTTPException(status_code=400, detail="Missing noc_no or ?no query parameter")
    data = load_mock_json("fire_noc_registry.json")
    record = data.get(lookup_key)
    if not record:
        raise HTTPException(status_code=404, detail=f"Fire NOC {lookup_key} not found")
    return record

# 2. Land Registry
@router.get("/land")
@router.get("/land/{deed_no:path}")
def get_land_record(deed_no: Optional[str] = None, no: Optional[str] = Query(default=None)):
    lookup_key = deed_no or no
    if not lookup_key:
        raise HTTPException(status_code=400, detail="Missing deed_no or ?no query parameter")
    data = load_mock_json("land_registry.json")
    record = data.get(lookup_key)
    if not record:
        raise HTTPException(status_code=404, detail=f"Land deed {lookup_key} not found")
    if record.get("response") == "PENDING":
        return JSONResponse(status_code=202, content={"status": "pending", "reference": lookup_key})
    return record

# 3. University Affiliation Registry
@router.get("/university/{code}")
@router.get("/university/{code}/{letter_no:path}")
def get_university_affiliation(
    code: str,
    letter_no: Optional[str] = None,
    no: Optional[str] = Query(default=None)
):
    univ_code = code.upper()
    data = load_mock_json("university_registry.json")
    univ_record = data.get(univ_code)
    if not univ_record:
        raise HTTPException(status_code=404, detail=f"University code {code} not found")
    
    # Check university registry availability
    if not univ_record.get("available", True):
        return JSONResponse(
            status_code=503,
            content={"detail": f"University registry for {univ_code} is currently unavailable", "available": False}
        )

    lookup_letter = letter_no or no
    if not lookup_letter:
        raise HTTPException(status_code=400, detail="Missing letter_no or ?no query parameter")

    letters = univ_record.get("letters", {})
    record = letters.get(lookup_letter)
    if not record:
        raise HTTPException(status_code=404, detail=f"Affiliation letter {lookup_letter} not found for university {code}")
    return record

# 4. Accreditation Registry
@router.get("/accreditation")
@router.get("/accreditation/{cert_no:path}")
def get_accreditation(cert_no: Optional[str] = None, no: Optional[str] = Query(default=None)):
    lookup_key = cert_no or no
    if not lookup_key:
        raise HTTPException(status_code=400, detail="Missing cert_no or ?no query parameter")
    data = load_mock_json("accreditation_registry.json")
    record = data.get(lookup_key)
    if not record:
        raise HTTPException(status_code=404, detail=f"Accreditation certificate {lookup_key} not found")
    return record

# 5. AICTE Historical Records
@router.get("/aicte")
@router.get("/aicte/{aicte_id:path}")
def get_aicte_record(aicte_id: Optional[str] = None, no: Optional[str] = Query(default=None)):
    lookup_key = aicte_id or no
    if not lookup_key:
        raise HTTPException(status_code=400, detail="Missing aicte_id or ?no query parameter")
    data = load_mock_json("aicte_records.json")
    record = data.get(lookup_key)
    if not record:
        raise HTTPException(status_code=404, detail=f"AICTE permanent record {lookup_key} not found")
    return record
