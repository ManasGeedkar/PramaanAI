import json
from typing import Dict, Any, List, Optional
from sqlmodel import Session, select
from app.config import settings
from app.models import Application, Finding


def calculate_risk(app: Application, session: Session) -> Dict[str, Any]:
    """
    Computes explainable risk triage score, risk band, and breakdown
    per data/config/risk.yaml.
    Stores risk_score, risk_band, and risk_breakdown_json on Application.
    """
    risk_cfg = settings.risk or {}
    points_cfg = risk_cfg.get("points", {})
    bands_cfg = risk_cfg.get("bands", {"High": 60, "Medium": 20, "Low": 0})

    findings = session.exec(
        select(Finding).where(
            Finding.application_id == app.id,
            Finding.status != "dismissed"
        )
    ).all()

    breakdown: List[Dict[str, Any]] = []
    has_statutory_expired = False
    has_source_mismatch = False
    has_no_prev_record = False

    for f in findings:
        # Base severity points
        if f.code in ("SOURCE_UNAVAILABLE", "VERIFICATION_PENDING"):
            base_pts = points_cfg.get("source_unavailable", 0)
        elif f.severity == "critical":
            base_pts = points_cfg.get("critical_finding", 30)
        elif f.severity == "warning":
            base_pts = points_cfg.get("warning_finding", 10)
        else:
            base_pts = points_cfg.get("info_finding", 0)

        if base_pts > 0:
            breakdown.append({
                "reason": f"{f.title} ({f.severity.upper()})",
                "points": base_pts,
                "finding_id": f.id
            })

        # Check conditions
        if f.code in ("EXPIRED_DOC", "SOURCE_EXPIRED"):
            has_statutory_expired = True

        if f.code == "SOURCE_MISMATCH":
            has_source_mismatch = True

        if f.code == "NO_PREVIOUS_RECORD":
            has_no_prev_record = True

        # Duplicate entity / image points (per finding)
        if f.code in ("ENTITY_REUSE", "DUPLICATE_IMAGE"):
            dup_pts = points_cfg.get("duplicate_entity", 15)
            breakdown.append({
                "reason": f"Duplicate entity / image ({f.code})",
                "points": dup_pts,
                "finding_id": f.id
            })

    # Additional contextual points added once per application
    if has_statutory_expired:
        pts = points_cfg.get("expired_statutory_doc", 25)
        breakdown.append({
            "reason": "Expired statutory document (Fire Safety NOC)",
            "points": pts,
            "finding_id": None
        })

    if has_source_mismatch:
        pts = points_cfg.get("source_mismatch", 25)
        breakdown.append({
            "reason": "Source registry verification mismatch",
            "points": pts,
            "finding_id": None
        })

    if has_no_prev_record:
        pts = points_cfg.get("missing_previous_year_record", 10)
        breakdown.append({
            "reason": "Missing previous year AICTE approved record",
            "points": pts,
            "finding_id": None
        })

    total_score = sum(item["points"] for item in breakdown)

    # Determine risk band
    if total_score >= bands_cfg.get("High", 60):
        band = "High"
    elif total_score >= bands_cfg.get("Medium", 20):
        band = "Medium"
    else:
        band = "Low"

    app.risk_score = float(total_score)
    app.risk_band = band
    app.risk_breakdown_json = json.dumps(breakdown)

    session.add(app)
    session.commit()
    session.refresh(app)

    return {
        "risk_score": app.risk_score,
        "risk_band": app.risk_band,
        "breakdown": breakdown
    }
