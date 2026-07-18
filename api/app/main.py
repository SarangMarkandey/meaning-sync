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
    WorkflowErrorCode,
    WorkflowErrorDetail,
    WorkflowErrorResponse,
)
from app.services.analyzers import OpenAIAgreementAnalyzer
from app.services.live_access import LiveAccessService
from app.services.live_sessions import LiveSessionService


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
    application.state.live_session_service = LiveSessionService(
        analyzer=OpenAIAgreementAnalyzer(settings=settings),
        repository=repository,
        clarification_attempt_limit=settings.meaningsync_clarification_attempt_limit,
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
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
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
