from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
import yaml
from sqlmodel import Session, select

from app.db import get_session
from app.models import RuleSet, Application, Finding
from app.config import settings
from app.services.audit import log_audit
from app.pipeline.run import run_pipeline

router = APIRouter(prefix="/api/rules", tags=["rules"])

class RuleUpdatePayload(BaseModel):
    yaml_text: str

@router.get("")
def get_active_rules(session: Session = Depends(get_session)):
    active_ruleset = session.exec(
        select(RuleSet).where(RuleSet.active == True)
    ).first()

    if not active_ruleset:
        # Create from rules.yaml if not in DB yet
        raw_yaml = settings.raw_rules_yaml()
        version = settings.rules.get("version", "2027-28.v1") if settings.rules else "2027-28.v1"
        active_ruleset = RuleSet(
            version=version,
            yaml_text=raw_yaml,
            active=True
        )
        session.add(active_ruleset)
        session.commit()
        session.refresh(active_ruleset)

    return {
        "id": active_ruleset.id,
        "version": active_ruleset.version,
        "yaml_text": active_ruleset.yaml_text,
        "active": active_ruleset.active,
        "created_at": active_ruleset.created_at
    }

@router.put("")
def update_rules(
    payload: RuleUpdatePayload,
    session: Session = Depends(get_session)
):
    try:
        parsed_yaml = yaml.safe_load(payload.yaml_text)
        if not isinstance(parsed_yaml, dict):
            raise ValueError("YAML content must be a valid mapping")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML content: {e}")

    version = parsed_yaml.get("version", f"v{int(datetime.utcnow().timestamp())}")

    # Record previous finding counts per application
    apps = session.exec(select(Application)).all()
    before_counts: Dict[int, int] = {}
    for a in apps:
        findings = session.exec(select(Finding).where(Finding.application_id == a.id)).all()
        before_counts[a.id] = len(findings)

    # Deactivate current active rulesets
    current_active = session.exec(select(RuleSet).where(RuleSet.active == True)).all()
    for rs in current_active:
        rs.active = False
        session.add(rs)

    # Save new RuleSet
    new_ruleset = RuleSet(
        version=version,
        yaml_text=payload.yaml_text,
        active=True
    )
    session.add(new_ruleset)
    session.commit()
    session.refresh(new_ruleset)

    # Update in-memory settings
    settings.rules = parsed_yaml

    # Re-run all applications
    changed_counts: Dict[str, int] = {}
    for a in apps:
        run_pipeline(a.id, session)
        new_findings = session.exec(select(Finding).where(Finding.application_id == a.id)).all()
        delta = len(new_findings) - before_counts.get(a.id, 0)
        changed_counts[a.institution_id] = delta

    # Write audit log row
    log_audit(
        session=session,
        actor="admin",
        action="rules_update",
        entity_type="ruleset",
        entity_id=new_ruleset.id,
        payload={
            "version": version,
            "changed_counts": changed_counts
        }
    )

    return {
        "version": version,
        "active": True,
        "changed_counts": changed_counts
    }
