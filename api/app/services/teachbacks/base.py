from typing import Protocol

from app.schemas.teachback import (
    TeachbackErrorCode,
    TeachbackEvaluation,
    TeachbackEvaluationRequest,
)


class TeachbackFailure(Exception):
    def __init__(
        self,
        code: TeachbackErrorCode,
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


class TeachbackEvaluator(Protocol):
    async def evaluate(
        self, request: TeachbackEvaluationRequest
    ) -> TeachbackEvaluation: ...
