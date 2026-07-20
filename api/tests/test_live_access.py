from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select, update

from alembic import command
from app.main import app, lifespan
from app.repositories.live_access import LiveAccessRow, LiveInvitationRow
from app.schemas.workflow import LiveParticipationMode
from app.services.live_access import AccessFailure
from app.services.transcriptions import (
    FakeRealtimeSessionInitializer,
    RealtimeTranscriptionService,
)
from tests.test_live_workflow import create_submission


@asynccontextmanager
async def api_client():
    async with (
        lifespan(app),
        AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        yield client


@pytest.fixture
def access_database_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path / 'live-access.sqlite3'}"
    monkeypatch.setenv("MEANINGSYNC_DATABASE_URL", url)
    monkeypatch.setenv("MEANINGSYNC_ACCESS_TOKEN_TTL_HOURS", "24")
    monkeypatch.setenv("MEANINGSYNC_INVITE_TTL_MINUTES", "15")
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    command.upgrade(config, "head")
    return url


def separate_submission() -> dict:
    return (
        create_submission()
        .model_copy(
            update={
                "messages": [],
                "participation_mode": LiveParticipationMode.SEPARATE_DEVICES,
            }
        )
        .model_dump(mode="json")
    )


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_realtime_initialization_is_role_scoped_and_returns_only_sdp(
    access_database_url: str,
) -> None:
    submission = create_submission().model_copy(update={"messages": []})
    async with api_client() as client:
        app.state.realtime_transcription_service = RealtimeTranscriptionService(
            FakeRealtimeSessionInitializer(), max_concurrent_per_participant=1
        )
        created = await client.post(
            "/api/v1/live/sessions", json=submission.model_dump(mode="json")
        )
        body = created.json()
        session_id = body["id"]
        tokens = {
            item["role"]: item["access_token"] for item in body["access_credentials"]
        }
        init_headers = {
            **bearer(tokens["hirer"]),
            "Content-Type": "application/sdp",
            "X-MeaningSync-Revision": "1",
            "X-Request-ID": "init-before-consent",
        }
        missing = await client.post(
            f"/api/v1/live/sessions/{session_id}/transcription-session",
            headers=init_headers,
            content="v=0\r\ns=offer\r\n",
        )
        assert missing.status_code == 409
        assert missing.json()["detail"]["code"] == "audio_consent_required"

        consented = await client.post(
            f"/api/v1/live/sessions/{session_id}/audio-consent",
            headers=bearer(tokens["hirer"]),
            json={
                "accepted": True,
                "notice_version": "audio-transcription-v1",
                "expected_revision": 1,
                "request_id": "hirer-audio-consent",
            },
        )
        assert consented.status_code == 200
        assert consented.json()["audio_consents"]["hirer"]["participant_role"] == (
            "hirer"
        )

        initialized = await client.post(
            f"/api/v1/live/sessions/{session_id}/transcription-session",
            headers={
                **bearer(tokens["hirer"]),
                "Content-Type": "application/sdp",
                "X-MeaningSync-Revision": "2",
                "X-Request-ID": "hirer-realtime-init",
            },
            content="v=0\r\ns=offer\r\n",
        )
        assert initialized.status_code == 200
        assert initialized.headers["content-type"].startswith("application/sdp")
        assert initialized.text.startswith("v=0")
        assert initialized.text.endswith("\r\n")
        assert "key" not in initialized.text.lower()
        assert "token" not in initialized.text.lower()

        worker = await client.post(
            f"/api/v1/live/sessions/{session_id}/transcription-session",
            headers={
                **bearer(tokens["worker"]),
                "Content-Type": "application/sdp",
                "X-MeaningSync-Revision": "2",
                "X-Request-ID": "worker-realtime-init",
            },
            content="v=0\r\ns=offer\r\n",
        )
        assert worker.status_code == 409
        assert worker.json()["detail"]["code"] == "audio_consent_required"


@pytest.mark.anyio
async def test_separate_session_requires_role_bound_bearer_access(
    access_database_url: str,
) -> None:
    async with api_client() as client:
        created = await client.post("/api/v1/live/sessions", json=separate_submission())
        assert created.status_code == 201
        body = created.json()
        session_id = body["id"]
        host_token = body["access_credentials"][0]["access_token"]
        invitation = body["invitation"]["invitation"]

        missing = await client.get(f"/api/v1/live/sessions/{session_id}")
        assert missing.status_code == 401
        assert missing.json()["detail"]["code"] == "access_required"

        declined = await client.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": invitation, "privacy_notice_accepted": False},
        )
        assert declined.status_code == 422

        joined = await client.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": invitation, "privacy_notice_accepted": True},
        )
        assert joined.status_code == 200
        worker_token = joined.json()["access_token"]

        host_view = await client.get(
            f"/api/v1/live/sessions/{session_id}", headers=bearer(host_token)
        )
        worker_view = await client.get(
            f"/api/v1/live/sessions/{session_id}", headers=bearer(worker_token)
        )
        assert host_view.json()["viewer_role"] == "hirer"
        assert worker_view.json()["viewer_role"] == "worker"
        assert host_view.headers["etag"] == '"1"'

        forbidden = await client.post(
            f"/api/v1/live/sessions/{session_id}/analysis",
            headers=bearer(worker_token),
            json={"expected_agreement_version_id": None},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["detail"]["code"] == "role_forbidden"

        another = (
            await client.post("/api/v1/live/sessions", json=separate_submission())
        ).json()
        cross_session = await client.get(
            f"/api/v1/live/sessions/{session_id}",
            headers=bearer(another["access_credentials"][0]["access_token"]),
        )
        assert cross_session.status_code == 403
        assert cross_session.json()["detail"]["code"] == "role_forbidden"


@pytest.mark.anyio
async def test_service_provider_can_create_and_invites_customer(
    access_database_url: str,
) -> None:
    submission = separate_submission()
    submission["creator_role"] = "worker"
    submission["currency"] = "USD"
    async with api_client() as client:
        created = await client.post("/api/v1/live/sessions", json=submission)
        assert created.status_code == 201
        body = created.json()
        assert body["creator_role"] == "worker"
        assert body["currency"] == "USD"
        assert body["access_credentials"][0]["role"] == "worker"
        assert body["invitation"]["role"] == "hirer"


@pytest.mark.anyio
async def test_invitation_is_single_use_and_replacement_revokes_old_secret(
    access_database_url: str,
) -> None:
    async with api_client() as client:
        body = (
            await client.post("/api/v1/live/sessions", json=separate_submission())
        ).json()
        session_id = body["id"]
        host_token = body["access_credentials"][0]["access_token"]
        old_invitation = body["invitation"]["invitation"]
        replacement = await client.post(
            f"/api/v1/live/sessions/{session_id}/invitations/regenerate",
            headers=bearer(host_token),
        )
        assert replacement.status_code == 200
        new_invitation = replacement.json()["invitation"]["invitation"]

        revoked = await client.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": old_invitation, "privacy_notice_accepted": True},
        )
        assert revoked.status_code == 410
        assert revoked.json()["detail"]["code"] == "invitation_revoked"

        first = await client.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": new_invitation, "privacy_notice_accepted": True},
        )
        second = await client.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": new_invitation, "privacy_notice_accepted": True},
        )
        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "invitation_used"


@pytest.mark.anyio
async def test_only_hashes_are_persisted_and_access_survives_restart(
    access_database_url: str,
) -> None:
    async with api_client() as client:
        body = (
            await client.post("/api/v1/live/sessions", json=separate_submission())
        ).json()
        session_id = body["id"]
        host_token = body["access_credentials"][0]["access_token"]
        invitation = body["invitation"]["invitation"]

    engine = create_engine(access_database_url)
    with engine.connect() as connection:
        token_hash = connection.execute(select(LiveAccessRow.token_hash)).scalar_one()
        invitation_hash = connection.execute(
            select(LiveInvitationRow.invitation_hash)
        ).scalar_one()
    engine.dispose()
    assert token_hash != host_token and len(token_hash) == 64
    assert invitation_hash != invitation and len(invitation_hash) == 64

    async with api_client() as restarted:
        recovered = await restarted.get(
            f"/api/v1/live/sessions/{session_id}", headers=bearer(host_token)
        )
        exchanged = await restarted.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": invitation, "privacy_notice_accepted": True},
        )
    assert recovered.status_code == 200
    assert exchanged.status_code == 200


@pytest.mark.anyio
async def test_concurrent_invitation_exchange_has_exactly_one_winner(
    access_database_url: str,
) -> None:
    async with api_client() as client:
        invitation = (
            await client.post("/api/v1/live/sessions", json=separate_submission())
        ).json()["invitation"]["invitation"]
        access_service = app.state.live_access_service

        def exchange() -> str:
            try:
                access_service.exchange(invitation)
                return "accepted"
            except AccessFailure as exc:
                return exc.code.value

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: exchange(), range(8)))

    assert results.count("accepted") == 1
    assert results.count("invitation_used") == 7


@pytest.mark.anyio
async def test_revoked_participant_credential_stops_working(
    access_database_url: str,
) -> None:
    async with api_client() as client:
        body = (
            await client.post("/api/v1/live/sessions", json=separate_submission())
        ).json()
        session_id = body["id"]
        host_token = body["access_credentials"][0]["access_token"]
        joined = (
            await client.post(
                "/api/v1/live/invitations/exchange",
                json={
                    "invitation": body["invitation"]["invitation"],
                    "privacy_notice_accepted": True,
                },
            )
        ).json()
        worker_token = joined["access_token"]
        revoked = await client.post(
            f"/api/v1/live/sessions/{session_id}/participants/worker/revoke",
            headers=bearer(host_token),
        )
        after = await client.get(
            f"/api/v1/live/sessions/{session_id}", headers=bearer(worker_token)
        )
    assert revoked.status_code == 204
    assert after.status_code == 401
    assert after.json()["detail"]["code"] == "access_revoked"


@pytest.mark.anyio
async def test_expired_access_and_invitation_return_distinct_errors(
    access_database_url: str,
) -> None:
    async with api_client() as client:
        body = (
            await client.post("/api/v1/live/sessions", json=separate_submission())
        ).json()
        session_id = body["id"]
        host_token = body["access_credentials"][0]["access_token"]
        invitation = body["invitation"]["invitation"]
        engine = create_engine(access_database_url)
        expired_at = datetime.now(UTC) - timedelta(minutes=1)
        with engine.begin() as connection:
            connection.execute(
                update(LiveAccessRow)
                .where(LiveAccessRow.session_id == session_id)
                .values(expires_at=expired_at)
            )
            connection.execute(
                update(LiveInvitationRow)
                .where(LiveInvitationRow.session_id == session_id)
                .values(expires_at=expired_at)
            )
        engine.dispose()

        expired_access = await client.get(
            f"/api/v1/live/sessions/{session_id}", headers=bearer(host_token)
        )
        expired_invite = await client.post(
            "/api/v1/live/invitations/exchange",
            json={"invitation": invitation, "privacy_notice_accepted": True},
        )

    assert expired_access.status_code == 401
    assert expired_access.json()["detail"]["code"] == "access_expired"
    assert expired_invite.status_code == 410
    assert expired_invite.json()["detail"]["code"] == "invitation_expired"
