from __future__ import annotations

import asyncio
import json
from time import monotonic
from typing import Protocol

import httpx

from app.config import Settings


class TranscriptionInitializationFailure(Exception):
    """A sanitized, recoverable Realtime initialization failure."""


class RealtimeSessionInitializer(Protocol):
    async def initialize(
        self,
        *,
        sdp: str,
        model: str,
        language: str,
        timeout_seconds: float,
    ) -> str: ...


class OpenAIRealtimeSessionInitializer:
    """Backend-only unified WebRTC call initialization."""

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.openai_api_key

    async def initialize(
        self,
        *,
        sdp: str,
        model: str,
        language: str,
        timeout_seconds: float,
    ) -> str:
        if self._api_key is None:
            raise TranscriptionInitializationFailure(
                "Live transcription is not configured. Continue with text."
            )
        session = {
            "type": "transcription",
            "audio": {
                "input": {
                    "transcription": {"model": model, "language": language},
                    "turn_detection": None,
                }
            },
        }
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/realtime/calls",
                    headers={
                        "Authorization": f"Bearer {self._api_key.get_secret_value()}"
                    },
                    files={
                        "sdp": (None, sdp, "application/sdp"),
                        "session": (
                            None,
                            json.dumps(session, separators=(",", ":")),
                            "application/json",
                        ),
                    },
                )
                response.raise_for_status()
                # SDP is line-oriented and its final line terminator is significant to
                # browser parsers. Forward the provider response without trimming it.
                answer = response.text
                if not answer.startswith("v=0"):
                    raise TranscriptionInitializationFailure(
                        "OpenAI returned an invalid WebRTC response. Continue "
                        "with text."
                    )
                return answer
        except TranscriptionInitializationFailure:
            raise
        except (httpx.HTTPError, TimeoutError) as exc:
            raise TranscriptionInitializationFailure(
                "Live transcription is temporarily unavailable. Try again or "
                "continue with text."
            ) from exc


class FakeRealtimeSessionInitializer:
    def __init__(self, *, answer_sdp: str = "v=0\r\ns=fake-answer\r\n") -> None:
        self.answer_sdp = answer_sdp
        self.calls: list[dict[str, str | float]] = []

    async def initialize(
        self,
        *,
        sdp: str,
        model: str,
        language: str,
        timeout_seconds: float,
    ) -> str:
        self.calls.append(
            {
                "sdp": sdp,
                "model": model,
                "language": language,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.answer_sdp


class FailingRealtimeSessionInitializer:
    async def initialize(
        self,
        *,
        sdp: str,
        model: str,
        language: str,
        timeout_seconds: float,
    ) -> str:
        raise TranscriptionInitializationFailure(
            "Live transcription is temporarily unavailable. Try again or "
            "continue with text."
        )


class RealtimeTranscriptionService:
    """Limits overlapping initializers without persisting ephemeral call state."""

    def __init__(
        self,
        initializer: RealtimeSessionInitializer,
        *,
        max_concurrent_per_participant: int,
        lease_seconds: float = 90,
    ) -> None:
        self._initializer = initializer
        self._maximum = max_concurrent_per_participant
        self._lease_seconds = lease_seconds
        self._active: dict[tuple[str, str], list[float]] = {}
        self._lock = asyncio.Lock()

    async def _reserve(self, session_id: str, role: str) -> None:
        key = (session_id, role)
        async with self._lock:
            now = monotonic()
            active = [expiry for expiry in self._active.get(key, []) if expiry > now]
            if len(active) >= self._maximum:
                raise TranscriptionInitializationFailure(
                    "A microphone connection is already being started for this "
                    "participant."
                )
            self._active[key] = [*active, now + self._lease_seconds]

    async def release(self, *, session_id: str, role: str) -> None:
        key = (session_id, role)
        async with self._lock:
            active = self._active.get(key, [])
            if len(active) <= 1:
                self._active.pop(key, None)
            else:
                self._active[key] = active[1:]

    async def initialize(
        self,
        *,
        session_id: str,
        role: str,
        sdp: str,
        model: str,
        language: str,
        timeout_seconds: float,
    ) -> str:
        await self._reserve(session_id, role)
        try:
            return await self._initializer.initialize(
                sdp=sdp,
                model=model,
                language=language,
                timeout_seconds=timeout_seconds,
            )
        except Exception:
            await self.release(session_id=session_id, role=role)
            raise
