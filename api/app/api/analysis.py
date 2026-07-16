from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.analysis import (
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AnalysisErrorCode,
    AnalysisErrorDetail,
    AnalysisErrorResponse,
    SessionMode,
)
from app.services.analyzers import (
    AgreementAnalyzer,
    AnalysisFailure,
    OpenAIAgreementAnalyzer,
)

router = APIRouter(prefix="/api/v1/agreements", tags=["agreement analysis"])


def get_live_analyzer() -> AgreementAnalyzer:
    return OpenAIAgreementAnalyzer()


@router.post(
    "/analyze",
    response_model=AgreementAnalysisResponse,
    responses={
        422: {"model": AnalysisErrorResponse},
        429: {"model": AnalysisErrorResponse},
        502: {"model": AnalysisErrorResponse},
        503: {"model": AnalysisErrorResponse},
        504: {"model": AnalysisErrorResponse},
    },
)
async def analyze_agreement(
    submission: AgreementAnalysisRequest,
    analyzer: Annotated[AgreementAnalyzer, Depends(get_live_analyzer)],
) -> AgreementAnalysisResponse:
    if submission.mode != SessionMode.LIVE:
        detail = AnalysisErrorDetail(
            code=AnalysisErrorCode.INVALID_REQUEST,
            message="This endpoint accepts Live Text Analysis requests only.",
            retryable=False,
        )
        raise HTTPException(status_code=422, detail=detail.model_dump(mode="json"))
    try:
        return await analyzer.analyze(submission)
    except AnalysisFailure as exc:
        detail = AnalysisErrorDetail(
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
        )
        raise HTTPException(
            status_code=exc.status_code,
            detail=detail.model_dump(mode="json"),
        ) from exc
