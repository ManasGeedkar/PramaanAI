import io
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlmodel import Session
from PIL import Image

from app.db import get_session
from app.models import Finding, Application, Review, Document
from app.services.audit import log_audit
from app.pipeline.risk import calculate_risk
from app.services.brief import generate_full_line_crop, generate_ela_crop

router = APIRouter(prefix="/api/findings", tags=["findings"])


class ReviewRequest(BaseModel):
    decision: str  # accept | dismiss | request_evidence | escalate
    comment: Optional[str] = None
    reviewer: Optional[str] = "Scrutiny Officer"


@router.post("/{id}/review")
def review_finding(
    id: int,
    req: ReviewRequest,
    session: Session = Depends(get_session)
):
    finding = session.get(Finding, id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    app = session.get(Application, finding.application_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    decision_norm = req.decision.lower().strip()
    valid_decisions = {"accept", "dismiss", "request_evidence", "escalate"}
    if decision_norm not in valid_decisions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid decision '{req.decision}'. Must be one of: {', '.join(sorted(valid_decisions))}"
        )

    # Update finding status (matching section 4.1 finding status)
    status_map = {
        "accept": "accepted",
        "dismiss": "dismissed",
        "request_evidence": "evidence_requested",
        "escalate": "escalated"
    }
    finding.status = status_map.get(decision_norm, decision_norm)

    # Update application status
    if decision_norm == "escalate":
        app.status = "escalated"
    elif decision_norm == "request_evidence":
        app.status = "evidence_requested"
    else:  # accept or dismiss
        if app.status not in ("escalated", "evidence_requested"):
            app.status = "under_review"

    # Create Review record
    review = Review(
        finding_id=finding.id,
        reviewer=req.reviewer or "Scrutiny Officer",
        decision=decision_norm,
        comment=req.comment,
        created_at=datetime.utcnow().isoformat()
    )
    session.add(review)

    # Write Audit log
    log_audit(
        session=session,
        actor=req.reviewer or "Scrutiny Officer",
        action=f"REVIEW_{decision_norm.upper()}",
        entity_type="Finding",
        entity_id=str(finding.id),
        payload={
            "decision": decision_norm,
            "comment": req.comment,
            "finding_code": finding.code,
            "application_id": app.id,
            "application_status": app.status
        }
    )

    session.add(finding)
    session.add(app)
    session.commit()
    session.refresh(finding)
    session.refresh(app)

    # Recalculate application risk score & band (dismissed findings add 0)
    risk_info = calculate_risk(app, session)

    return {
        "ok": True,
        "finding": {
            "id": finding.id,
            "code": finding.code,
            "status": finding.status
        },
        "application": {
            "id": app.id,
            "status": app.status,
            "risk_score": app.risk_score,
            "risk_band": app.risk_band,
            "risk_breakdown": risk_info.get("breakdown", [])
        },
        "review": {
            "id": review.id,
            "reviewer": review.reviewer,
            "decision": review.decision,
            "comment": review.comment,
            "created_at": review.created_at
        }
    }


@router.get("/{id}/ela-crop.png")
def get_finding_ela_crop(
    id: int,
    session: Session = Depends(get_session)
):
    finding = session.get(Finding, id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    if not finding.document_id:
        raise HTTPException(status_code=400, detail="Finding has no associated document")

    doc = session.get(Document, finding.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    bbox = None
    if finding.evidence_json:
        try:
            ev = json.loads(finding.evidence_json)
            items = ev.get("items", [])
            if items and items[0].get("bbox"):
                bbox = items[0]["bbox"]
        except Exception:
            pass

    if not bbox:
        raise HTTPException(status_code=400, detail="Finding has no evidence bounding box")

    doc_crop_bytes, crop_rect, pdoc = generate_full_line_crop(doc, bbox)
    if not doc_crop_bytes or not crop_rect:
        if pdoc:
            pdoc.close()
        raise HTTPException(status_code=500, detail="Failed to generate document line crop")

    ela_crop_bytes = generate_ela_crop(doc, crop_rect)
    if pdoc:
        pdoc.close()

    if not ela_crop_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate ELA crop")

    # Stack document line crop above ELA crop
    im_doc = Image.open(io.BytesIO(doc_crop_bytes)).convert("RGB")
    im_ela = Image.open(io.BytesIO(ela_crop_bytes)).convert("RGB")

    target_w = max(im_doc.width, im_ela.width)
    if im_doc.width != target_w:
        im_doc = im_doc.resize((target_w, int(im_doc.height * target_w / im_doc.width)), Image.Resampling.LANCZOS)
    if im_ela.width != target_w:
        im_ela = im_ela.resize((target_w, int(im_ela.height * target_w / im_ela.width)), Image.Resampling.LANCZOS)

    gap = 4
    stacked_h = im_doc.height + im_ela.height + gap
    stacked = Image.new("RGB", (target_w, stacked_h), color=(30, 41, 59))
    stacked.paste(im_doc, (0, 0))
    stacked.paste(im_ela, (0, im_doc.height + gap))

    out_buf = io.BytesIO()
    stacked.save(out_buf, format="PNG")
    return Response(content=out_buf.getvalue(), media_type="image/png")

