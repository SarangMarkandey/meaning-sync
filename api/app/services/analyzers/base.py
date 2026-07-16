from typing import Protocol

from app.schemas.analysis import (
    AgreementAnalysisRequest,
    AgreementAnalysisResponse,
    AnalysisErrorCode,
)


class AnalysisFailure(Exception):
    def __init__(
        self,
        code: AnalysisErrorCode,
        message: str,
        *,
        retryable: bool,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.status_code = status_code


class AgreementAnalyzer(Protocol):
    async def analyze(
        self, request: AgreementAnalysisRequest
    ) -> AgreementAnalysisResponse: ...
