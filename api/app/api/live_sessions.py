from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from app.schemas.analysis import AnalysisErrorResponse, PartyRole
from app.schemas.understanding import (
    LeaveQuestionUnresolvedSubmission,
    UnderstandingSelectionSubmission,
)
from app.schemas.workflow import (
    AdditionalStatementsSubmission,
    AgreementVersion,
    AnalyzeLiveSessionSubmission,
    AudioConsentSubmission,
    ConfirmationStatusView,
    ConfirmationSubmission,
    ConversationReentrySubmission,
    DraftStatementSubmission,
    FinalizedAudioTranscriptSubmission,
    IssueReceiptSubmission,
    LiveClarityReceipt,
    LiveInvitationExchange,
    LiveInvitationExchangeResult,
    LiveInvitationResult,
    LiveParticipationMode,
    LiveSessionCreate,
    LiveSessionCreateResult,
    LiveSessionView,
    NotApplicableProposalSubmission,
    OptionalDetailsReviewedSubmission,
    ParticipantReadinessSubmission,
    StartUnderstandingCheckSubmission,
    WorkflowErrorCode,
    WorkflowErrorDetail,
    WorkflowErrorResponse,
)
from app.services.analyzers import AnalysisFailure
from app.services.live_access import AccessContext, AccessFailure, LiveAccessService
from app.services.live_sessions import LiveSessionService, WorkflowFailure
from app.services.transcriptions import (
    RealtimeTranscriptionService,
    TranscriptionInitializationFailure,
)

router = APIRouter(prefix="/api/v1/live/sessions", tags=["live sessions"])
invitation_router = APIRouter(prefix="/api/v1/live/invitations", tags=["live sessions"])


async def get_live_session_service(request: Request) -> LiveSessionService:
    service = getattr(request.app.state, "live_session_service", None)
    if service is None:
        raise RuntimeError("Live session repository is not initialized")
    return service


Service = Annotated[LiveSessionService, Depends(get_live_session_service)]
Authorization = Annotated[str | None, Header(alias="Authorization")]


def get_realtime_transcription_service(
    request: Request,
) -> RealtimeTranscriptionService:
    service = getattr(request.app.state, "realtime_transcription_service", None)
    if service is None:
        raise RuntimeError("Realtime transcription service is not initialized")
    return service


def get_live_access_service(request: Request) -> LiveAccessService:
    service = getattr(request.app.state, "live_access_service", None)
    if service is None:
        raise RuntimeError("Live access repository is not initialized")
    return service


def _access_error(exc: AccessFailure) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code.value, "message": exc.message, "retryable": False},
    )


def _authorize(
    request: Request,
    authorization: str | None,
    session_id: str,
    role=None,
) -> AccessContext:
    raw = None
    if authorization and authorization.startswith("Bearer "):
        raw = authorization.removeprefix("Bearer ").strip()
    try:
        return get_live_access_service(request).authenticate(
            raw, session_id=session_id, role=role
        )
    except AccessFailure as exc:
        raise _access_error(exc) from exc


def _other_role(role: PartyRole) -> PartyRole:
    return PartyRole.WORKER if role == PartyRole.HIRER else PartyRole.HIRER


def _authorize_creator(
    request: Request,
    authorization: str | None,
    session_id: str,
    service: LiveSessionService,
) -> AccessContext:
    return _authorize(
        request,
        authorization,
        session_id,
        role=service.get(session_id).creator_role,
    )


def _scoped_view(
    request: Request,
    service: LiveSessionService,
    session_id: str,
    context: AccessContext,
) -> LiveSessionView:
    view, revision = service.get_with_revision(session_id)
    return view.model_copy(
        update={
            "revision": revision,
            "viewer_role": context.role,
            "participant_presence": get_live_access_service(request).presence(
                session_id
            ),
        }
    )


ERROR_RESPONSES = {
    401: {"model": WorkflowErrorResponse},
    403: {"model": WorkflowErrorResponse},
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


@invitation_router.post(
    "/exchange",
    response_model=LiveInvitationExchangeResult,
    responses=ERROR_RESPONSES,
)
async def exchange_live_invitation(
    submission: LiveInvitationExchange, request: Request
) -> LiveInvitationExchangeResult:
    try:
        return get_live_access_service(request).exchange(submission.invitation)
    except AccessFailure as exc:
        raise _access_error(exc) from exc


@router.post(
    "",
    response_model=LiveSessionCreateResult,
    status_code=201,
    responses=ERROR_RESPONSES,
)
async def create_live_session(
    submission: LiveSessionCreate, service: Service, request: Request
) -> LiveSessionCreateResult:
    try:
        created = service.create(submission)
        access = get_live_access_service(request)
        credentials = [access.issue_access(created.id, created.creator_role)]
        invitation = None
        if submission.participation_mode == LiveParticipationMode.SAME_DEVICE:
            credentials.append(
                access.issue_access(created.id, _other_role(created.creator_role))
            )
        else:
            invitation = access.issue_invitation(
                created.id, _other_role(created.creator_role)
            )
        context = AccessContext(
            created.id, credentials[0].role, credentials[0].expires_at
        )
        view = _scoped_view(request, service, created.id, context)
        return LiveSessionCreateResult(
            **view.model_dump(mode="python"),
            access_credentials=credentials,
            invitation=invitation,
        )
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get("/{session_id}", response_model=LiveSessionView, responses=ERROR_RESPONSES)
async def get_live_session(
    session_id: str,
    service: Service,
    request: Request,
    response: Response,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        view = _scoped_view(request, service, session_id, context)
        response.headers["ETag"] = f'"{view.revision}"'
        return view
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/draft-statements",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def add_draft_statement(
    session_id: str,
    submission: DraftStatementSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        service.add_draft_statement(session_id, context.role, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/audio-consent",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def record_audio_consent(
    session_id: str,
    submission: AudioConsentSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        service.record_audio_consent(session_id, context.role, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/transcription-session",
    response_class=Response,
    responses=ERROR_RESPONSES,
)
async def initialize_transcription_session(
    session_id: str,
    request: Request,
    service: Service,
    expected_revision: Annotated[int, Header(alias="X-MeaningSync-Revision", ge=1)],
    request_id: Annotated[
        str, Header(alias="X-Request-ID", min_length=1, max_length=80)
    ],
    authorization: Authorization = None,
) -> Response:
    del request_id
    try:
        context = _authorize(request, authorization, session_id)
        language, configuration = service.authorize_transcription_initialization(
            session_id,
            context.role,
            expected_revision=expected_revision,
        )
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/sdp":
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_REQUEST,
                "Realtime initialization requires an application/sdp offer.",
                status_code=422,
            )
        raw_offer = await request.body()
        if len(raw_offer) > 200_000:
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_REQUEST,
                "The WebRTC offer is too large.",
                status_code=422,
            )
        try:
            offer = raw_offer.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_REQUEST,
                "The WebRTC offer is invalid.",
                status_code=422,
            ) from exc
        if not offer.strip().startswith("v=0"):
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_REQUEST,
                "The WebRTC offer is invalid.",
                status_code=422,
            )
        answer = await get_realtime_transcription_service(request).initialize(
            session_id=session_id,
            role=context.role.value,
            sdp=offer,
            model=configuration.model,
            language=language,
            timeout_seconds=configuration.initialization_timeout_seconds,
        )
        return Response(
            content=answer,
            media_type="application/sdp",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
        )
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
    except TranscriptionInitializationFailure as exc:
        raise _workflow_error(
            WorkflowFailure(
                WorkflowErrorCode.TRANSCRIPTION_UNAVAILABLE,
                str(exc),
                status_code=503,
                retryable=True,
            )
        ) from exc


@router.post(
    "/{session_id}/audio-transcripts",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def add_audio_transcript(
    session_id: str,
    submission: FinalizedAudioTranscriptSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        service.add_audio_transcript(session_id, context.role, submission)
        await get_realtime_transcription_service(request).release(
            session_id=session_id, role=context.role.value
        )
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/transcription-session/end",
    status_code=204,
    responses=ERROR_RESPONSES,
)
async def end_transcription_session(
    session_id: str,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> Response:
    try:
        context = _authorize(request, authorization, session_id)
        view = service.get(session_id)
        if view.stage.value != "conversation_draft":
            raise WorkflowFailure(
                WorkflowErrorCode.INVALID_STATE,
                "Microphone transcription is available only during Conversation.",
                status_code=409,
            )
        await get_realtime_transcription_service(request).release(
            session_id=session_id, role=context.role.value
        )
        return Response(status_code=204)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/readiness",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def set_participant_readiness(
    session_id: str,
    submission: ParticipantReadinessSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        service.set_participant_readiness(session_id, context.role, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/conversation/reentry",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def reenter_live_conversation(
    session_id: str,
    submission: ConversationReentrySubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        service.reenter_conversation(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/invitations/regenerate",
    response_model=LiveInvitationResult,
    responses=ERROR_RESPONSES,
)
async def regenerate_live_invitation(
    session_id: str,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveInvitationResult:
    context = _authorize_creator(request, authorization, session_id, service)
    invitation = get_live_access_service(request).issue_invitation(
        session_id, _other_role(context.role)
    )
    return LiveInvitationResult(session_id=session_id, invitation=invitation)


@router.post(
    "/{session_id}/participants/{role}/revoke",
    status_code=204,
    responses=ERROR_RESPONSES,
)
async def revoke_live_participant(
    session_id: str,
    role: PartyRole,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> Response:
    context = _authorize_creator(request, authorization, session_id, service)
    if role == context.role:
        raise HTTPException(
            status_code=422,
            detail={
                "code": WorkflowErrorCode.INVALID_REQUEST.value,
                "message": "The creator cannot revoke their current credential.",
                "retryable": False,
            },
        )
    get_live_access_service(request).revoke_role(session_id, role)
    return Response(status_code=204)


@router.post(
    "/{session_id}/analysis",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def analyze_live_session(
    session_id: str,
    submission: AnalyzeLiveSessionSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize_creator(request, authorization, session_id, service)
        await service.analyze(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
    except AnalysisFailure as exc:
        raise _provider_error(exc) from exc


@router.get(
    "/{session_id}/agreement-versions",
    response_model=list[AgreementVersion],
    responses=ERROR_RESPONSES,
)
async def list_agreement_versions(
    session_id: str,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> list[AgreementVersion]:
    try:
        _authorize(request, authorization, session_id)
        return service.list_versions(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{session_id}/agreement-versions/{version_id}",
    response_model=AgreementVersion,
    responses=ERROR_RESPONSES,
)
async def get_agreement_version(
    session_id: str,
    version_id: str,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> AgreementVersion:
    try:
        _authorize(request, authorization, session_id)
        return service.get_version(session_id, version_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/questions/{question_id}/selections",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def submit_understanding_selection(
    session_id: str,
    question_id: str,
    submission: UnderstandingSelectionSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(
            request, authorization, session_id, role=submission.participant_id
        )
        service.submit_selection(session_id, question_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/questions/{question_id}/leave-unresolved",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def leave_question_unresolved(
    session_id: str,
    question_id: str,
    submission: LeaveQuestionUnresolvedSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(
            request, authorization, session_id, role=submission.participant_id
        )
        service.leave_question_unresolved(session_id, question_id, submission)
        return _scoped_view(request, service, session_id, context)
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
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(request, authorization, session_id)
        if any(
            message.speaker_id != context.role.value for message in submission.messages
        ):
            raise AccessFailure(
                WorkflowErrorCode.ROLE_FORBIDDEN,
                "A participant may submit only their own statements.",
                status_code=403,
            )
        await service.add_statements(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except AccessFailure as exc:
        raise _access_error(exc) from exc
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
    except AnalysisFailure as exc:
        raise _provider_error(exc) from exc


@router.post(
    "/{session_id}/not-applicable",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def propose_not_applicable(
    session_id: str,
    submission: NotApplicableProposalSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(
            request, authorization, session_id, role=submission.participant_id
        )
        service.propose_not_applicable(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/optional-details/reviewed",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def mark_optional_details_reviewed(
    session_id: str,
    submission: OptionalDetailsReviewedSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize_creator(request, authorization, session_id, service)
        service.mark_optional_details_reviewed(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/understanding-checks",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def start_understanding_check(
    session_id: str,
    submission: StartUnderstandingCheckSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize_creator(request, authorization, session_id, service)
        service.start_understanding_check(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/confirmations",
    response_model=LiveSessionView,
    responses=ERROR_RESPONSES,
)
async def submit_confirmation(
    session_id: str,
    submission: ConfirmationSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveSessionView:
    try:
        context = _authorize(
            request, authorization, session_id, role=submission.participant_id
        )
        service.submit_confirmation(session_id, submission)
        return _scoped_view(request, service, session_id, context)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{session_id}/confirmation-status",
    response_model=ConfirmationStatusView,
    responses=ERROR_RESPONSES,
)
async def get_confirmation_status(
    session_id: str,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> ConfirmationStatusView:
    try:
        _authorize(request, authorization, session_id)
        return service.confirmation_status(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.post(
    "/{session_id}/receipt",
    response_model=LiveClarityReceipt,
    responses=ERROR_RESPONSES,
)
async def issue_clarity_receipt(
    session_id: str,
    submission: IssueReceiptSubmission,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveClarityReceipt:
    try:
        _authorize_creator(request, authorization, session_id, service)
        return service.issue_receipt(session_id, submission)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc


@router.get(
    "/{session_id}/receipt",
    response_model=LiveClarityReceipt,
    responses=ERROR_RESPONSES,
)
async def get_clarity_receipt(
    session_id: str,
    service: Service,
    request: Request,
    authorization: Authorization = None,
) -> LiveClarityReceipt:
    try:
        _authorize(request, authorization, session_id)
        return service.get_receipt(session_id)
    except WorkflowFailure as exc:
        raise _workflow_error(exc) from exc
