from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.analysis import AnalysisErrorResponse
from app.schemas.understanding import (
    LeaveQuestionUnresolvedSubmission,
    UnderstandingSelectionSubmission,
)
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AgreementVersion,
    AnalyzeLiveSessionSubmission,
    ConfirmationStatusView,
    ConfirmationSubmission,
    IssueReceiptSubmission,
    LiveClarityReceipt,
    LiveSessionCreate,
    LiveSessionView,
    NotApplicableProposalSubmission,
    OptionalDetailsReviewedSubmission,
    StartUnderstandingCheckSubmission,
    WorkflowErrorDetail,
    WorkflowErrorResponse,
)
from app.services.analyzers import AnalysisFailure
from app.services.live_sessions import LiveSessionService, WorkflowFailure

router = APIRouter(prefix="/api/v1/live/sessions", tags=["live sessions"])


def get_live_session_service(request: Request) -> LiveSessionService:
    service = getattr(request.app.state, "live_session_service", None)
    if service is None:
        raise RuntimeError("Live session repository is not initialized")
    return service


Service = Annotated[LiveSessionService, Depends(get_live_session_service)]


ERROR_RESPONSES = {
    404: {"model": WorkflowErrorResponse},
    410: {"model": WorkflowErrorResponse},
    409: {"model": WorkflowErrorResponse},
    422: {"model": WorkflowErrorResponse},
    429: {"model": AnalysisErrorResponse},
    502: {"model": AnalysisErrorResponse},
    503: {"model": AnalysisErrorResponse},
    504: {"model": AnalysisErrorResponse},
    500: {"model": WorkflowErrorResponse},
}


def _workflow_error(exc: WorkflowFailure) -> HTTPException:
    detail = WorkflowErrorDetail(
        code=exc.code,
        message=exc.message,
        retryable=exc.retryable,
        current_agreement_version_id=exc.current_agreement_version_id,
    )
    return HTTPException(
        status_code=exc.status_code,
        detail=detail.model_dump(mode="json"),
    )


def _provider_error(exc: AnalysisFailure) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code.value,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    )


@router.post(
    "", response_model=LiveSessionView, status_code=201, responses=ERROR_RESPONSES
)
def create_live_session(
    submission: LiveSessionCreate, service: Service
) -> LiveSessionView:
    try:
        return service.create(submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get("/{session_id}", response_model=LiveSessionView, responses=ERROR_RESPONSES)
def get_live_session(session_id: str, service: Service) -> LiveSessionView:
    try:
        return service.get(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/analysis",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def analyze_live_session(
    session_id: str,
    submission: AnalyzeLiveSessionSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return await service.analyze(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
    except AnalysisFailure as exc:
        raise _provider_error(exc) from exc


@router.get(
    "/{session_id}/agreement-versions",
    response_model=list[AgreementVersion],
    responses=ERROR_RESPONSES,
)
def list_agreement_versions(
    session_id: str, service: Service
) -> list[AgreementVersion]:
    try:
        return service.list_versions(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{session_id}/agreement-versions/{version_id}",
    response_model=AgreementVersion,
    responses=ERROR_RESPONSES,
)
def get_agreement_version(
    session_id: str, version_id: str, service: Service
) -> AgreementVersion:
    try:
        return service.get_version(session_id, version_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/questions/{question_id}/selections",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
def submit_understanding_selection(
    session_id: str,
    question_id: str,
    submission: UnderstandingSelectionSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return service.submit_selection(session_id, question_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/questions/{question_id}/leave-unresolved",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
def leave_question_unresolved(
    session_id: str,
    question_id: str,
    submission: LeaveQuestionUnresolvedSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return service.leave_question_unresolved(session_id, question_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/statements",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def add_live_statements(
    session_id: str,
    submission: AdditionalStatementsSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return await service.add_statements(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
    except AnalysisFailure as exc:
        raise _provider_error(exc) from exc


@router.post(
    "/{session_id}/not-applicable",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
def propose_not_applicable(
    session_id: str,
    submission: NotApplicableProposalSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return service.propose_not_applicable(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/optional-details/reviewed",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
def mark_optional_details_reviewed(
    session_id: str,
    submission: OptionalDetailsReviewedSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return service.mark_optional_details_reviewed(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/understanding-checks",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
def start_understanding_check(
    session_id: str,
    submission: StartUnderstandingCheckSubmission,
    service: Service,
) -> LiveSessionView:
    try:
        return service.start_understanding_check(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/confirmations",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
def submit_confirmation(
    session_id: str, submission: ConfirmationSubmission, service: Service
) -> LiveSessionView:
    try:
        return service.submit_confirmation(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{session_id}/confirmation-status",
    response_model=ConfirmationStatusView,
    responses=ERROR_RESPONSES,
)
def get_confirmation_status(
    session_id: str, service: Service
) -> ConfirmationStatusView:
    try:
        return service.confirmation_status(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/receipt",
    response_model=LiveClarityReceipt,
    responses=ERROR_RESPONSES,
)
def issue_clarity_receipt(
    session_id: str, submission: IssueReceiptSubmission, service: Service
) -> LiveClarityReceipt:
    try:
        return service.issue_receipt(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{session_id}/receipt",
    response_model=LiveClarityReceipt,
    responses=ERROR_RESPONSES,
)
def get_clarity_receipt(session_id: str, service: Service) -> LiveClarityReceipt:
    try:
        return service.get_receipt(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
