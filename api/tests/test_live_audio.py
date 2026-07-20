from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import Settings
from app.repositories import InMemoryLiveSessionRepository
from app.schemas.analysis import MessageInputSource, PartyRole
from app.schemas.workflow import (
    AnalyzeLiveSessionSubmission,
    AudioConsentSubmission,
    AudioTranscriptionConfiguration,
    FinalizedAudioTranscriptSubmission,
    IssueReceiptSubmission,
    LiveSessionCreate,
    ParticipantReadinessSubmission,
    WorkflowErrorCode,
)
from app.services.live_sessions import LiveSessionService, WorkflowFailure
from app.services.transcriptions import (
    FakeRealtimeSessionInitializer,
    OpenAIRealtimeSessionInitializer,
    RealtimeTranscriptionService,
    TranscriptionInitializationFailure,
)
from tests.test_live_workflow import (
    FixtureAnalyzer,
    complete_current_checks,
    confirm_both,
    participants,
    resolve_initial_materials,
    start_check,
)


def audio_configuration(**updates) -> AudioTranscriptionConfiguration:
    values = {
        "model": "gpt-realtime-whisper",
        "consent_notice_version": "audio-transcription-v1",
        "max_turn_duration_seconds": 60,
        "max_session_duration_seconds_per_participant": 120,
        "initialization_timeout_seconds": 8,
        "idle_timeout_seconds": 15,
        "max_transcript_length": 2000,
        "max_concurrent_sessions_per_participant": 1,
    }
    values.update(updates)
    return AudioTranscriptionConfiguration(**values)


def workflow(**configuration_updates) -> LiveSessionService:
    return LiveSessionService(
        analyzer=FixtureAnalyzer(),
        repository=InMemoryLiveSessionRepository(),
        audio_configuration=audio_configuration(**configuration_updates),
    )


def empty_session(service: LiveSessionService):
    return service.create(LiveSessionCreate(participants=participants()))


def consent(service: LiveSessionService, session_id: str, role: PartyRole):
    _, revision = service.get_with_revision(session_id)
    return service.record_audio_consent(
        session_id,
        role,
        AudioConsentSubmission(
            accepted=True,
            notice_version="audio-transcription-v1",
            expected_revision=revision,
            request_id=f"consent-{role.value}",
        ),
    )


def transcript_submission(
    service: LiveSessionService, session_id: str, role: PartyRole, **updates
):
    view, revision = service.get_with_revision(session_id)
    started = datetime(2026, 7, 19, 10, tzinfo=UTC)
    values = {
        "raw_transcript": "The labour price is twelve hundred rupees.",
        "corrected_text": "The labour price is ₹1,200.",
        "started_at": started,
        "completed_at": started + timedelta(seconds=4),
        "duration_seconds": 4,
        "transcription_model": "gpt-realtime-whisper",
        "consent_id": view.audio_consents[role].id,
        "expected_revision": revision,
        "request_id": f"transcript-{role.value}",
    }
    values.update(updates)
    return FinalizedAudioTranscriptSubmission(**values)


def test_consent_is_role_bound_versioned_and_timestamped() -> None:
    service = workflow()
    created = empty_session(service)
    view = consent(service, created.id, PartyRole.HIRER)

    record = view.audio_consents[PartyRole.HIRER]
    assert record.session_id == created.id
    assert record.participant_role == PartyRole.HIRER
    assert record.notice_version == "audio-transcription-v1"
    assert record.consented_at.tzinfo is not None
    assert PartyRole.WORKER not in view.audio_consents

    with pytest.raises(WorkflowFailure) as failure:
        service.authorize_transcription_initialization(
            created.id,
            PartyRole.WORKER,
            expected_revision=service.get_with_revision(created.id)[1],
        )
    assert failure.value.code == WorkflowErrorCode.AUDIO_CONSENT_REQUIRED


def test_audio_initialization_requires_consent_and_current_revision() -> None:
    service = workflow()
    created = empty_session(service)
    with pytest.raises(WorkflowFailure) as missing:
        service.authorize_transcription_initialization(
            created.id, PartyRole.HIRER, expected_revision=1
        )
    assert missing.value.code == WorkflowErrorCode.AUDIO_CONSENT_REQUIRED

    consent(service, created.id, PartyRole.HIRER)
    with pytest.raises(WorkflowFailure) as stale:
        service.authorize_transcription_initialization(
            created.id, PartyRole.HIRER, expected_revision=1
        )
    assert stale.value.code == WorkflowErrorCode.CONCURRENT_UPDATE


@pytest.mark.anyio
async def test_fake_initializer_uses_secure_transcription_configuration() -> None:
    fake = FakeRealtimeSessionInitializer()
    service = RealtimeTranscriptionService(fake, max_concurrent_per_participant=1)
    answer = await service.initialize(
        session_id="live-1",
        role="hirer",
        sdp="v=0\r\ns=offer\r\n",
        model="gpt-realtime-whisper",
        language="en",
        timeout_seconds=8,
    )
    assert answer.startswith("v=0")
    assert fake.calls == [
        {
            "sdp": "v=0\r\ns=offer\r\n",
            "model": "gpt-realtime-whisper",
            "language": "en",
            "timeout_seconds": 8,
        }
    ]
    with pytest.raises(TranscriptionInitializationFailure):
        await service.initialize(
            session_id="live-1",
            role="hirer",
            sdp="v=0\r\ns=second-offer\r\n",
            model="gpt-realtime-whisper",
            language="en",
            timeout_seconds=8,
        )
    await service.release(session_id="live-1", role="hirer")
    assert (
        await service.initialize(
            session_id="live-1",
            role="hirer",
            sdp="v=0\r\ns=third-offer\r\n",
            model="gpt-realtime-whisper",
            language="en",
            timeout_seconds=8,
        )
    ).startswith("v=0")


@pytest.mark.anyio
async def test_openai_initializer_preserves_sdp_line_terminator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answer_sdp = (
        "v=0\r\n"
        "o=- 1 1 IN IP4 127.0.0.1\r\n"
        "s=-\r\n"
        "t=0 0\r\n"
        "a=ice-pwd:abcdefghijklmnopqrstuvwxyz123456\r\n"
    )

    class StubAsyncClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 8

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            return None

        async def post(self, url: str, **kwargs) -> httpx.Response:
            assert url == "https://api.openai.com/v1/realtime/calls"
            assert kwargs["files"]["sdp"][1].endswith("\r\n")
            return httpx.Response(
                201,
                content=answer_sdp.encode(),
                headers={"Content-Type": "application/sdp"},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr(
        "app.services.transcriptions.httpx.AsyncClient", StubAsyncClient
    )
    initializer = OpenAIRealtimeSessionInitializer(
        Settings(openai_api_key="test-api-key")
    )

    answer = await initializer.initialize(
        sdp="v=0\r\ns=test-offer\r\n",
        model="gpt-realtime-whisper",
        language="en",
        timeout_seconds=8,
    )

    assert answer == answer_sdp
    assert answer.endswith("\r\n")


def test_finalized_audio_preserves_raw_correction_effective_text_and_order() -> None:
    service = workflow()
    created = empty_session(service)
    consent(service, created.id, PartyRole.HIRER)
    submission = transcript_submission(service, created.id, PartyRole.HIRER)
    view = service.add_audio_transcript(created.id, PartyRole.HIRER, submission)

    message = view.messages[0]
    assert message.input_source == MessageInputSource.AUDIO_TRANSCRIPT
    assert message.raw_transcript == submission.raw_transcript
    assert message.corrected_text == submission.corrected_text
    assert message.effective_text == submission.corrected_text
    assert message.original_text == submission.corrected_text
    assert message.order == 1
    assert message.consent_id == view.audio_consents[PartyRole.HIRER].id
    assert view.participant_readiness == {
        PartyRole.HIRER: False,
        PartyRole.WORKER: False,
    }


def test_duplicate_transcript_is_idempotent_even_after_revision_changes() -> None:
    service = workflow()
    created = empty_session(service)
    consent(service, created.id, PartyRole.HIRER)
    submission = transcript_submission(service, created.id, PartyRole.HIRER)
    first = service.add_audio_transcript(created.id, PartyRole.HIRER, submission)
    replay = service.add_audio_transcript(created.id, PartyRole.HIRER, submission)
    assert len(first.messages) == len(replay.messages) == 1
    assert replay.messages[0].message_id == first.messages[0].message_id


def test_audio_rejected_after_readiness_and_when_limits_are_exceeded() -> None:
    service = workflow(max_turn_duration_seconds=5, max_transcript_length=30)
    created = empty_session(service)
    consent(service, created.id, PartyRole.HIRER)
    _, revision = service.get_with_revision(created.id)
    service.set_participant_readiness(
        created.id,
        PartyRole.HIRER,
        ParticipantReadinessSubmission(ready=True, request_id="ready-hirer"),
    )
    with pytest.raises(WorkflowFailure) as ready_failure:
        service.add_audio_transcript(
            created.id,
            PartyRole.HIRER,
            transcript_submission(
                service,
                created.id,
                PartyRole.HIRER,
                expected_revision=revision + 1,
            ),
        )
    assert ready_failure.value.code == WorkflowErrorCode.INVALID_STATE

    service.set_participant_readiness(
        created.id,
        PartyRole.HIRER,
        ParticipantReadinessSubmission(ready=False, request_id="not-ready-hirer"),
    )
    with pytest.raises(WorkflowFailure) as limit_failure:
        service.add_audio_transcript(
            created.id,
            PartyRole.HIRER,
            transcript_submission(
                service,
                created.id,
                PartyRole.HIRER,
                raw_transcript="A transcript that is deliberately much too long.",
                corrected_text=None,
                request_id="too-long",
            ),
        )
    assert limit_failure.value.code == WorkflowErrorCode.AUDIO_LIMIT_REACHED


@pytest.mark.anyio
async def test_analysis_and_receipt_evidence_keep_audio_provenance() -> None:
    service = workflow()
    created = empty_session(service)
    for role in PartyRole:
        consent(service, created.id, role)
        service.add_audio_transcript(
            created.id,
            role,
            transcript_submission(
                service,
                created.id,
                role,
                request_id=f"turn-{role.value}",
            ),
        )
    for role in PartyRole:
        service.set_participant_readiness(
            created.id,
            role,
            ParticipantReadinessSubmission(
                ready=True, request_id=f"ready-{role.value}"
            ),
        )
    analyzed = await service.analyze(created.id, AnalyzeLiveSessionSubmission())
    evidence = analyzed.current_version.terms[0].evidence
    assert all(
        item.input_source == MessageInputSource.AUDIO_TRANSCRIPT for item in evidence
    )
    assert all(item.raw_transcript for item in evidence)
    assert all(item.corrected_text for item in evidence)
    ready = resolve_initial_materials(service, analyzed)
    ready = complete_current_checks(service, start_check(service, ready))
    confirmed = confirm_both(service, ready)
    receipt = service.issue_receipt(
        created.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=confirmed.current_agreement_version_id,
            request_id="audio-receipt",
        ),
    )
    receipt_evidence = receipt.aligned_terms[0].evidence
    assert all(item.raw_transcript for item in receipt_evidence)


@pytest.mark.skipif(
    os.getenv("RUN_OPENAI_TRANSCRIPTION_INTEGRATION") != "1",
    reason="paid OpenAI Realtime transcription integration is opt-in",
)
@pytest.mark.anyio
async def test_paid_openai_realtime_initializer_is_explicitly_opt_in() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    offer_sdp = os.getenv("OPENAI_REALTIME_TEST_SDP")
    if not api_key or not offer_sdp:
        pytest.fail(
            "OPENAI_API_KEY and OPENAI_REALTIME_TEST_SDP are required for the "
            "opt-in test"
        )
    initializer = OpenAIRealtimeSessionInitializer(Settings(openai_api_key=api_key))
    answer = await initializer.initialize(
        sdp=offer_sdp,
        model="gpt-realtime-whisper",
        language="en",
        timeout_seconds=12,
    )
    assert answer.startswith("v=0")
