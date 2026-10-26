from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db import get_session
from app.services.evaluate import get_full_evaluation

router = APIRouter(prefix="/api/evaluate", tags=["evaluate"])

@router.get("")
def get_evaluation(session: Session = Depends(get_session)):
    return get_full_evaluation(session)

