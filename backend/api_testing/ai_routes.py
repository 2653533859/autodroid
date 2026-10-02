from fastapi import APIRouter, Depends
from sqlmodel import Session

from backend.api.deps import get_current_active_user
from backend.database import get_session
from backend.models import User
from . import ai_service
from .ai_schemas import ExplainFailureRequest, FeedbackRequest, SuggestAssertionsRequest

router = APIRouter(prefix="/ai", dependencies=[Depends(get_current_active_user)])


@router.get("/status")
def status(session: Session = Depends(get_session)):
    return ai_service.settings(session)[0]


@router.post("/suggest-assertions")
async def suggest_assertions(payload: SuggestAssertionsRequest, session: Session = Depends(get_session), user: User = Depends(get_current_active_user)):
    return await ai_service.suggest_assertions(payload, session, user.id)


@router.post("/explain-failure")
async def explain_failure(payload: ExplainFailureRequest, session: Session = Depends(get_session), user: User = Depends(get_current_active_user)):
    return await ai_service.explain_failure(payload, session, user.id)


@router.post("/feedback")
def feedback(payload: FeedbackRequest, user: User = Depends(get_current_active_user)):
    return ai_service.feedback(payload, user.id)
