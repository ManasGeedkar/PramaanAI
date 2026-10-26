from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import AuditLog
from app.services.audit import verify_chain

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def get_audit_logs(
    entity_id: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    application_id: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=1000),
    session: Session = Depends(get_session)
) -> List[AuditLog]:
    """
    Returns audit log entries, optionally filtered by application_id, entity_id or entity_type.
    """
    stmt = select(AuditLog)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    stmt = stmt.order_by(AuditLog.id.desc()).limit(limit)
    logs = session.exec(stmt).all()

    if application_id and application_id != "all":
        # Filter logs where entity_id matches or payload_json contains the application ID / number
        filtered = []
        for log in logs:
            match = False
            if log.entity_type == "application" and str(log.entity_id) == str(application_id):
                match = True
            elif log.payload_json and str(application_id) in log.payload_json:
                match = True
            if match:
                filtered.append(log)
        return filtered

    return logs


@router.get("/verify")
def verify_audit_chain(session: Session = Depends(get_session)) -> Dict[str, Any]:
    """
    Verifies the integrity of the SHA-256 hash chain for all audit logs.
    Returns: {"ok": bool, "broken_at": id | null}
    """
    return verify_chain(session)
