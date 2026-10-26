import hashlib
import json
from datetime import datetime
from typing import Any, Optional, Dict
from sqlmodel import Session, select
from app.models import AuditLog

GENESIS_HASH = "0" * 64

def calculate_hash(prev_hash: str, ts: str, actor: str, action: str, entity_type: str, entity_id: str, payload_json: Optional[str]) -> str:
    payload_str = payload_json if payload_json is not None else ""
    data = f"{prev_hash}{ts}{actor}{action}{entity_type}{entity_id}{payload_str}"
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def log_audit(
    session: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | int,
    payload: Any = None,
    ts: Optional[str] = None
) -> AuditLog:
    if ts is None:
        ts = datetime.utcnow().isoformat()

    entity_id_str = str(entity_id)
    
    if payload is None:
        payload_json = None
    elif isinstance(payload, str):
        payload_json = payload
    else:
        payload_json = json.dumps(payload, ensure_ascii=False)

    # Fetch previous log to get latest hash
    last_log = session.exec(
        select(AuditLog).order_by(AuditLog.id.desc())
    ).first()

    prev_hash = last_log.hash if last_log else GENESIS_HASH
    curr_hash = calculate_hash(prev_hash, ts, actor, action, entity_type, entity_id_str, payload_json)

    audit_entry = AuditLog(
        ts=ts,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id_str,
        payload_json=payload_json,
        prev_hash=prev_hash,
        hash=curr_hash
    )
    session.add(audit_entry)
    session.commit()
    session.refresh(audit_entry)
    return audit_entry

def verify_chain(session: Session) -> Dict[str, Any]:
    logs = session.exec(
        select(AuditLog).order_by(AuditLog.id.asc())
    ).all()

    if not logs:
        return {"ok": True, "broken_at": None}

    expected_prev_hash = GENESIS_HASH
    for log in logs:
        if log.prev_hash != expected_prev_hash:
            return {"ok": False, "broken_at": log.id}
        
        computed = calculate_hash(
            log.prev_hash,
            log.ts,
            log.actor,
            log.action,
            log.entity_type,
            log.entity_id,
            log.payload_json
        )
        if log.hash != computed:
            return {"ok": False, "broken_at": log.id}
        
        expected_prev_hash = log.hash

    return {"ok": True, "broken_at": None}
