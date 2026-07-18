from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select, update

from alembic import command
from app.main import app, lifespan
from app.repositories import (
    RepositoryConflict,
    SqlLiveSessionRepository,
)
from app.repositories.live_sessions import LiveSessionRow
from app.schemas.analysis import PartyRole
from app.schemas.understanding import (
    UnderstandingOptionKind,
    UnderstandingSelectionSubmission,
)
from app.schemas.workflow import (
    AnalyzeLiveSessionSubmission,
    CurrencyCode,
    IssueReceiptSubmission,
    LiveSessionStage,
    WorkflowErrorCode,
)
from app.services.live_sessions import LiveSessionService, WorkflowFailure
from tests.test_live_workflow import (
    FixtureAnalyzer,
    active_question,
    complete_current_checks,
    confirm_both,
    create_submission,
    option,
    resolve_initial_materials,
    start_check,
)


@pytest.fixture
def database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path / 'live-sessions.sqlite3'}"
    monkeypatch.setenv("MEANINGSYNC_DATABASE_URL", url)
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    return url


def repository(database_url: str, *, ttl_hours: int = 24):
    return SqlLiveSessionRepository(database_url, ttl_hours=ttl_hours)


def workflow(database_url: str, *, analyzer=None) -> LiveSessionService:
    return LiveSessionService(
        analyzer=analyzer or FixtureAnalyzer(),
        repository=repository(database_url),
    )


def test_state_v2_payload_upgrades_with_conversation_defaults(
    database_url: str,
) -> None:
    service = workflow(database_url)
    created = service.create(create_submission())
    service._repository.close()
    engine = create_engine(database_url)
    with engine.begin() as connection:
        payload = connection.execute(
            select(LiveSessionRow.state_json).where(LiveSessionRow.id == created.id)
        ).scalar_one()
        payload["state_schema_version"] = 2
        for field in (
            "currency",
            "creator_role",
            "participant_readiness",
            "conversation_reentry_item_key",
        ):
            payload.pop(field, None)
        connection.execute(
            update(LiveSessionRow)
            .where(LiveSessionRow.id == created.id)
            .values(state_schema_version=2, state_json=payload)
        )
    engine.dispose()

    recovered = repository(database_url).load(created.id).state
    assert recovered.state_schema_version == 3
    assert recovered.currency == CurrencyCode.INR
    assert recovered.creator_role == PartyRole.HIRER
    assert recovered.participant_readiness == {
        PartyRole.HIRER: False,
        PartyRole.WORKER: False,
    }
    assert recovered.conversation_reentry_item_key is None


@pytest.mark.anyio
async def test_fastapi_lifecycle_recovers_created_session_after_restart(
    database_url: str,
) -> None:
    async with (
        lifespan(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as first_client,
    ):
        response = await first_client.post(
            "/api/v1/live/sessions",
            json=create_submission().model_dump(mode="json"),
        )
        assert response.status_code == 201
        session_id = response.json()["id"]
        access_token = response.json()["access_credentials"][0]["access_token"]
    async with (
        lifespan(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as restarted_client,
    ):
        assert (await restarted_client.get("/health")).status_code == 200
        recovered = await restarted_client.get(
            f"/api/v1/live/sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    assert recovered.status_code == 200
    assert recovered.json()["id"] == session_id


@pytest.mark.anyio
async def test_durable_session_survives_new_repository_and_service(
    database_url: str,
) -> None:
    first = workflow(database_url)
    created = first.create(create_submission())
    analyzed = await first.analyze(created.id, AnalyzeLiveSessionSubmission())
    first._repository.close()

    second = workflow(database_url)
    recovered = second.get(created.id)
    assert recovered == analyzed
    assert recovered.stage == LiveSessionStage.NEEDS_CLARIFICATION


@pytest.mark.anyio
async def test_complete_state_and_receipt_round_trip_without_loss(
    database_url: str,
) -> None:
    first = workflow(database_url)
    session = first.create(create_submission())
    session = await first.analyze(session.id, AnalyzeLiveSessionSubmission())
    session = resolve_initial_materials(first, session)
    session = complete_current_checks(first, start_check(first, session))
    session = confirm_both(first, session)
    receipt = first.issue_receipt(
        session.id,
        IssueReceiptSubmission(
            expected_agreement_version_id=session.current_agreement_version_id,
            request_id="durable-receipt",
        ),
    )
    before = first._repository.load(session.id).state
    first._repository.close()

    second_repository = repository(database_url)
    after = second_repository.load(session.id).state
    assert after == before
    assert after.versions
    assert all(version.parent_version_id for version in after.versions[1:])
    assert after.questions and any(question.selections for question in after.questions)
    assert after.evidence_ledger
    assert len(after.confirmations) == 2
    assert after.processed_requests["durable-receipt"]
    assert after.receipt == receipt
    assert after.receipt.integrity_hash == receipt.integrity_hash


@pytest.mark.anyio
async def test_first_selection_remains_private_after_restart(
    database_url: str,
) -> None:
    first = workflow(database_url)
    session = first.create(create_submission())
    session = await first.analyze(session.id, AnalyzeLiveSessionSubmission())
    question = active_question(session)
    selected = option(question, UnderstandingOptionKind.RECORDED_POSITION)
    submission = UnderstandingSelectionSubmission(
        expected_agreement_version_id=session.current_agreement_version_id,
        participant_id=PartyRole.HIRER,
        option_id=selected.id,
        request_id="private-after-restart",
    )
    first.submit_selection(session.id, question.id, submission)
    first._repository.close()

    second = workflow(database_url)
    public = second.get(session.id)
    public_question = active_question(public)
    assert public_question.responses_revealed is False
    assert public_question.outcome is None
    assert public_question.answered_participant_ids == [PartyRole.HIRER]
    assert '"selections"' not in public.model_dump_json()


@pytest.mark.anyio
async def test_idempotency_and_payload_binding_survive_restart(
    database_url: str,
) -> None:
    first = workflow(database_url)
    session = first.create(create_submission())
    session = await first.analyze(session.id, AnalyzeLiveSessionSubmission())
    question = active_question(session)
    selected = option(question, UnderstandingOptionKind.RECORDED_POSITION)
    submission = UnderstandingSelectionSubmission(
        expected_agreement_version_id=session.current_agreement_version_id,
        participant_id=PartyRole.HIRER,
        option_id=selected.id,
        request_id="restart-idempotency",
    )
    successful = first.submit_selection(session.id, question.id, submission)
    revision = first._repository.load(session.id).revision
    first._repository.close()

    second = workflow(database_url)
    replay = second.submit_selection(session.id, question.id, submission)
    assert replay == successful
    assert second._repository.load(session.id).revision == revision

    other = option(question, UnderstandingOptionKind.OTHER)
    with pytest.raises(WorkflowFailure) as conflict:
        second.submit_selection(
            session.id,
            question.id,
            submission.model_copy(
                update={"option_id": other.id, "other_text": "Different meaning."}
            ),
        )
    assert conflict.value.code == WorkflowErrorCode.IDEMPOTENCY_CONFLICT


def test_stale_repository_revision_is_rejected_atomically(database_url: str) -> None:
    repo = repository(database_url)
    service = LiveSessionService(analyzer=FixtureAnalyzer(), repository=repo)
    created = service.create(create_submission())
    original_revision = repo.load(created.id).revision

    with repo.transaction(created.id, expected_revision=original_revision) as current:
        current.state.optional_details_reviewed = True

    with (
        pytest.raises(RepositoryConflict),
        repo.transaction(created.id, expected_revision=original_revision) as stale,
    ):
        stale.state.optional_details_reviewed = False
    stored = repo.load(created.id)
    assert stored.revision == original_revision + 1
    assert stored.state.optional_details_reviewed is True


@pytest.mark.anyio
async def test_failed_second_selection_has_no_partial_durable_mutation(
    database_url: str,
) -> None:
    first = workflow(database_url)
    session = first.create(create_submission())
    session = await first.analyze(session.id, AnalyzeLiveSessionSubmission())
    question = active_question(session)
    selected = option(question, UnderstandingOptionKind.RECORDED_POSITION)
    first_submission = UnderstandingSelectionSubmission(
        expected_agreement_version_id=session.current_agreement_version_id,
        participant_id=PartyRole.HIRER,
        option_id=selected.id,
        request_id="atomic-first-durable",
    )
    session = first.submit_selection(session.id, question.id, first_submission)

    def fail_completion(*args, **kwargs):
        raise RuntimeError("forced completion failure")

    first._complete_question = fail_completion
    second_submission = first_submission.model_copy(
        update={
            "participant_id": PartyRole.WORKER,
            "request_id": "atomic-second-durable",
        }
    )
    with pytest.raises(RuntimeError, match="forced completion failure"):
        first.submit_selection(session.id, question.id, second_submission)
    first._repository.close()

    second = workflow(database_url)
    public = second.get(session.id)
    stored = second._repository.load(session.id).state
    stored_question = next(
        item for item in stored.questions if item.question.id == question.id
    )
    assert set(stored_question.selections) == {PartyRole.HIRER}
    assert "atomic-second-durable" not in stored.processed_requests
    assert active_question(public).responses_revealed is False


class FailingAnalyzer:
    async def analyze(self, request):
        raise RuntimeError("offline analyzer failure")


@pytest.mark.anyio
async def test_failed_analysis_restores_retryable_state(database_url: str) -> None:
    first = workflow(database_url, analyzer=FailingAnalyzer())
    created = first.create(create_submission())
    with pytest.raises(RuntimeError, match="offline analyzer failure"):
        await first.analyze(created.id, AnalyzeLiveSessionSubmission())
    first._repository.close()

    second = workflow(database_url)
    recovered = second.get(created.id)
    assert recovered.stage == LiveSessionStage.CONVERSATION_DRAFT
    assert recovered.messages == created.messages


def test_expired_session_returns_controlled_response(database_url: str) -> None:
    service = workflow(database_url)
    created = service.create(create_submission())
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            update(LiveSessionRow)
            .where(LiveSessionRow.id == created.id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
    engine.dispose()

    with pytest.raises(WorkflowFailure) as expired:
        service.get(created.id)
    assert expired.value.code == WorkflowErrorCode.SESSION_EXPIRED
    assert expired.value.status_code == 410


def test_invalid_stored_state_returns_controlled_internal_error(
    database_url: str,
) -> None:
    service = workflow(database_url)
    created = service.create(create_submission())
    engine = create_engine(database_url)
    with engine.begin() as connection:
        payload = connection.execute(
            select(LiveSessionRow.state_json).where(LiveSessionRow.id == created.id)
        ).scalar_one()
        payload["unexpected_field"] = "unsafe"
        connection.execute(
            update(LiveSessionRow)
            .where(LiveSessionRow.id == created.id)
            .values(state_json=payload)
        )
    engine.dispose()

    with pytest.raises(WorkflowFailure) as invalid:
        service.get(created.id)
    assert invalid.value.code == WorkflowErrorCode.STORED_STATE_INVALID
    assert invalid.value.status_code == 500
