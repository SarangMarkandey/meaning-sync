from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.analysis import router as analysis_router
from app.api.live_sessions import invitation_router
from app.api.live_sessions import router as live_sessions_router
from app.api.sessions import router as sessions_router
from app.config import cors_origins, get_settings
from app.repositories import SqlLiveAccessRepository, SqlLiveSessionRepository
from app.schemas.analysis import (
    AnalysisErrorCode,
    AnalysisErrorDetail,
    AnalysisErrorResponse,
)
from app.schemas.workflow import (
    AudioTranscriptionConfiguration,
    WorkflowErrorCode,
    WorkflowErrorDetail,
    WorkflowErrorResponse,
)
from app.services.analyzers import OpenAIAgreementAnalyzer
from app.services.live_access import LiveAccessService
from app.services.live_sessions import LiveSessionService
from app.services.transcriptions import (
    OpenAIRealtimeSessionInitializer,
    RealtimeTranscriptionService,
)
from app.services.translation import OpenAITranslationService


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_settings()
    repository = SqlLiveSessionRepository(
        settings.meaningsync_database_url,
        ttl_hours=settings.meaningsync_session_ttl_hours,
    )
    repository.validate()
    access_repository = SqlLiveAccessRepository(settings.meaningsync_database_url)
    access_repository.validate()
    audio_configuration = AudioTranscriptionConfiguration(
        model=settings.openai_transcription_model,
        consent_notice_version=settings.meaningsync_audio_consent_notice_version,
        max_turn_duration_seconds=settings.meaningsync_audio_max_turn_seconds,
        max_session_duration_seconds_per_participant=(
            settings.meaningsync_audio_max_session_seconds_per_participant
        ),
        initialization_timeout_seconds=(
            settings.meaningsync_realtime_initialization_timeout_seconds
        ),
        idle_timeout_seconds=settings.meaningsync_audio_idle_timeout_seconds,
        max_transcript_length=settings.meaningsync_audio_max_transcript_length,
        max_concurrent_sessions_per_participant=(
            settings.meaningsync_audio_max_concurrent_sessions_per_participant
        ),
    )
    application.state.live_session_service = LiveSessionService(
        analyzer=OpenAIAgreementAnalyzer(settings=settings),
        repository=repository,
        clarification_attempt_limit=settings.meaningsync_clarification_attempt_limit,
        audio_configuration=audio_configuration,
        translation_service=OpenAITranslationService(settings=settings),
    )
    application.state.realtime_transcription_service = RealtimeTranscriptionService(
        OpenAIRealtimeSessionInitializer(settings),
        max_concurrent_per_participant=(
            audio_configuration.max_concurrent_sessions_per_participant
        ),
        lease_seconds=(
            audio_configuration.max_turn_duration_seconds
            + audio_configuration.idle_timeout_seconds
        ),
    )
    application.state.live_session_repository = repository
    application.state.live_access_service = LiveAccessService(
        access_repository,
        access_ttl_hours=settings.meaningsync_access_token_ttl_hours,
        invite_ttl_minutes=settings.meaningsync_invite_ttl_minutes,
    )
    application.state.live_access_repository = access_repository
    try:
        yield
    finally:
        repository.close()
        access_repository.close()


app = FastAPI(
    title="MeaningSync API",
    description=(
        "Deterministic demo and choice-based live agreement understanding checks."
    ),
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-MeaningSync-Revision",
        "X-Request-ID",
    ],
)
app.include_router(sessions_router)
app.include_router(analysis_router)
app.include_router(live_sessions_router)
app.include_router(invitation_router)


@app.exception_handler(RequestValidationError)
async def controlled_request_validation(
    request: Request, exc: RequestValidationError
) -> Response:
    if request.url.path == "/api/v1/agreements/analyze":
        problem = AnalysisErrorResponse(
            detail=AnalysisErrorDetail(
                code=AnalysisErrorCode.INVALID_REQUEST,
                message="The agreement-analysis request is invalid.",
                retryable=False,
            )
        )
        return JSONResponse(status_code=422, content=problem.model_dump(mode="json"))
    if request.url.path.startswith(
        ("/api/v1/live/sessions", "/api/v1/live/invitations")
    ):
        problem = WorkflowErrorResponse(
            detail=WorkflowErrorDetail(
                code=WorkflowErrorCode.INVALID_REQUEST,
                message="The Live session request is invalid.",
                retryable=False,
            )
        )
        return JSONResponse(status_code=422, content=problem.model_dump(mode="json"))
    return await request_validation_exception_handler(request, exc)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
