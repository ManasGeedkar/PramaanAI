from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func

from app.db import get_session
from app.models import Application, Document, Finding, Verification
from app.config import settings

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
def get_system_stats(session: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Returns aggregated metrics for the overview & management dashboard:
    - Counts by risk band (High, Medium, Low)
    - Counts by verification status (6 statuses)
    - Documents auto-cleared
    - Estimated hours saved per data/config/risk.yaml formula
    """
    risk_cfg = settings.risk or {}
    effort_cfg = risk_cfg.get("manual_effort_assumptions", {})
    min_doc = effort_cfg.get("minutes_per_document_manual", 6)
    min_flag = effort_cfg.get("minutes_per_flagged_item_review", 4)
    assumption_note = effort_cfg.get(
        "note",
        "Hours saved = (all docs x 6 min) - (flagged items x 4 min). Simulated estimate for the prototype."
    )

    # 1. Applications by risk band
    apps = session.exec(select(Application)).all()
    total_apps = len(apps)
    by_band = {"High": 0, "Medium": 0, "Low": 0}
    for a in apps:
        band = a.risk_band or "Low"
        if band in by_band:
            by_band[band] += 1
        else:
            by_band[band] = 1

    # 2. Verifications by status
    statuses = [
        "verified",
        "mismatch",
        "expired",
        "pending",
        "source_unavailable",
        "manual_review"
    ]
    by_verification_status = {s: 0 for s in statuses}
    verifications = session.exec(select(Verification)).all()
    for v in verifications:
        if v.status in by_verification_status:
            by_verification_status[v.status] += 1
        else:
            by_verification_status[v.status] = 1

    # 3. Documents auto-cleared & total docs
    all_docs = session.exec(select(Document)).all()
    total_documents = len(all_docs)

    # A document is auto-cleared if it has no open critical or warning findings
    flagged_findings = session.exec(
        select(Finding).where(
            Finding.severity.in_(["critical", "warning"]),
            Finding.status != "dismissed"
        )
    ).all()
    flagged_findings_count = len(flagged_findings)

    # Set of document IDs that have critical or warning findings
    flagged_doc_ids = {f.document_id for f in flagged_findings if f.document_id is not None}

    # Documents with non-verified verification status
    non_verified_doc_ids = {
        v.document_id for v in verifications if v.status in ["mismatch", "expired", "manual_review"]
    }

    auto_cleared_count = 0
    for doc in all_docs:
        if doc.id not in flagged_doc_ids and doc.id not in non_verified_doc_ids:
            auto_cleared_count += 1

    # 4. Hours saved
    # Formula: (all docs * 6 min - flagged items * 4 min) / 60
    total_minutes_saved = (total_documents * min_doc) - (flagged_findings_count * min_flag)
    hours_saved = max(0.0, round(total_minutes_saved / 60.0, 1))

    return {
        "total_applications": total_apps,
        "high_risk_count": by_band.get("High", 0),
        "by_band": by_band,
        "by_verification_status": by_verification_status,
        "total_documents": total_documents,
        "documents_auto_cleared": auto_cleared_count,
        "flagged_findings_count": flagged_findings_count,
        "hours_saved": hours_saved,
        "hours_saved_assumption": assumption_note
    }
