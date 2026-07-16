from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from app.api.analysis import router as analysis_router
from app.api.sessions import router as sessions_router
from app.config import cors_origins
from app.schemas.analysis import (
    AnalysisErrorCode,
    AnalysisErrorDetail,
    AnalysisErrorResponse,
)

app = FastAPI(
    title="MeaningSync API",
    description="Deterministic demo and OpenAI-powered live agreement analysis.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(sessions_router)
app.include_router(analysis_router)


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
    return await request_validation_exception_handler(request, exc)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
