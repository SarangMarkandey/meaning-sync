from fastapi import APIRouter

from app.schemas.session import (
    ClarificationAnswerSubmission,
    ClarificationResult,
    ClarityReceipt,
    ConfirmationSubmission,
    ConsentSubmission,
    DemoSessionCreate,
    SessionView,
)
from app.services.sessions import session_service

router = APIRouter(prefix="/api/v1/demo/sessions", tags=["demo sessions"])


@router.post("", response_model=SessionView, status_code=201)
async def create_demo_session(
    submission: DemoSessionCreate | None = None,
) -> SessionView:
    languages = submission.participant_languages if submission else None
    currency = submission.currency if submission else None
    return session_service.create_demo(languages, currency or "INR")


@router.get("/{session_id}", response_model=SessionView)
async def get_demo_session(session_id: str) -> SessionView:
    return session_service.get(session_id)


@router.post("/{session_id}/consent", response_model=SessionView)
async def submit_consent(session_id: str, submission: ConsentSubmission) -> SessionView:
    return session_service.submit_consent(
        session_id, submission.party, submission.accepted
    )


@router.post("/{session_id}/analysis", response_model=SessionView)
async def analyze_demo_session(session_id: str) -> SessionView:
    return await session_service.analyze(session_id)


@router.post("/{session_id}/clarifications", response_model=SessionView)
async def begin_clarification(session_id: str) -> SessionView:
    return session_service.begin_clarification(session_id)


@router.post(
    "/{session_id}/clarifications/{question_id}/answers",
    response_model=ClarificationResult,
)
async def submit_clarification_answer(
    session_id: str,
    question_id: str,
    submission: ClarificationAnswerSubmission,
) -> ClarificationResult:
    return session_service.answer(
        session_id, question_id, submission.party, submission.answer
    )


@router.post("/{session_id}/confirmations", response_model=SessionView)
async def submit_confirmation(
    session_id: str, submission: ConfirmationSubmission
) -> SessionView:
    return session_service.confirm(
        session_id,
        submission.party,
        submission.confirmed,
        submission.teachback,
    )


@router.post("/{session_id}/receipt", response_model=ClarityReceipt)
async def create_clarity_receipt(session_id: str) -> ClarityReceipt:
    return session_service.create_receipt(session_id)
