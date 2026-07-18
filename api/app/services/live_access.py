from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.repositories import (
    AccessExpired,
    AccessNotFound,
    AccessRevoked,
    InvitationExpired,
    InvitationNotFound,
    InvitationRevoked,
    InvitationUsed,
    LiveAccessRepository,
    StoredAccess,
)
from app.schemas.analysis import PartyRole
from app.schemas.workflow import (
    LiveAccessCredential,
    LiveInvitation,
    LiveInvitationExchangeResult,
    ParticipantPresence,
    WorkflowErrorCode,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _secret() -> str:
    return secrets.token_urlsafe(32)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AccessContext:
    session_id: str
    role: PartyRole
    expires_at: datetime


class AccessFailure(Exception):
    def __init__(
        self, code: WorkflowErrorCode, message: str, *, status_code: int
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class LiveAccessService:
    def __init__(
        self,
        repository: LiveAccessRepository,
        *,
        access_ttl_hours: int = 24,
        invite_ttl_minutes: int = 15,
    ) -> None:
        self._repository = repository
        self._access_ttl = timedelta(hours=access_ttl_hours)
        self._invite_ttl = timedelta(minutes=invite_ttl_minutes)

    def issue_access(self, session_id: str, role: PartyRole) -> LiveAccessCredential:
        raw = _secret()
        expires_at = _now() + self._access_ttl
        self._repository.create_access(
            access_id=f"access-{uuid4().hex}",
            session_id=session_id,
            role=role,
            token_hash=_hash(raw),
            expires_at=expires_at,
        )
        return LiveAccessCredential(role=role, access_token=raw, expires_at=expires_at)

    def issue_invitation(self, session_id: str, role: PartyRole) -> LiveInvitation:
        raw = _secret()
        expires_at = _now() + self._invite_ttl
        self._repository.create_invitation(
            invitation_id=f"invite-{uuid4().hex}",
            session_id=session_id,
            role=role,
            invitation_hash=_hash(raw),
            expires_at=expires_at,
        )
        return LiveInvitation(role=role, invitation=raw, expires_at=expires_at)

    def exchange(self, invitation: str) -> LiveInvitationExchangeResult:
        raw_access = _secret()
        expires_at = _now() + self._access_ttl
        try:
            stored = self._repository.exchange_invitation(
                invitation_hash=_hash(invitation),
                access_id=f"access-{uuid4().hex}",
                access_hash=_hash(raw_access),
                access_expires_at=expires_at,
            )
        except InvitationNotFound as exc:
            raise AccessFailure(
                WorkflowErrorCode.INVITATION_INVALID,
                "This joining invitation is not valid.",
                status_code=401,
            ) from exc
        except InvitationExpired as exc:
            raise AccessFailure(
                WorkflowErrorCode.INVITATION_EXPIRED,
                "This joining invitation has expired. Ask the host for a new one.",
                status_code=410,
            ) from exc
        except InvitationUsed as exc:
            raise AccessFailure(
                WorkflowErrorCode.INVITATION_USED,
                "This joining invitation has already been used.",
                status_code=409,
            ) from exc
        except InvitationRevoked as exc:
            raise AccessFailure(
                WorkflowErrorCode.INVITATION_REVOKED,
                "This joining invitation was replaced. Ask the host for a new one.",
                status_code=410,
            ) from exc
        return LiveInvitationExchangeResult(
            session_id=stored.session_id,
            role=stored.role,
            access_token=raw_access,
            expires_at=expires_at,
        )

    def authenticate(
        self, raw_token: str | None, *, session_id: str, role: PartyRole | None = None
    ) -> AccessContext:
        if not raw_token:
            raise AccessFailure(
                WorkflowErrorCode.ACCESS_REQUIRED,
                "A Live participant access credential is required.",
                status_code=401,
            )
        try:
            stored = self._repository.authenticate(_hash(raw_token))
        except AccessNotFound as exc:
            raise AccessFailure(
                WorkflowErrorCode.ACCESS_INVALID,
                "The Live participant access credential is invalid.",
                status_code=401,
            ) from exc
        except AccessExpired as exc:
            raise AccessFailure(
                WorkflowErrorCode.ACCESS_EXPIRED,
                "This Live participant access credential has expired.",
                status_code=401,
            ) from exc
        except AccessRevoked as exc:
            raise AccessFailure(
                WorkflowErrorCode.ACCESS_REVOKED,
                "This Live participant access credential was revoked.",
                status_code=401,
            ) from exc
        if stored.session_id != session_id or (
            role is not None and stored.role != role
        ):
            raise AccessFailure(
                WorkflowErrorCode.ROLE_FORBIDDEN,
                "This participant credential cannot perform that action.",
                status_code=403,
            )
        return AccessContext(stored.session_id, stored.role, stored.expires_at)

    def revoke_role(self, session_id: str, role: PartyRole) -> None:
        self._repository.revoke_access(session_id, role)
        self._repository.revoke_invitations(session_id, role)

    def presence(self, session_id: str) -> list[ParticipantPresence]:
        now = _now()
        records = self._repository.presence(session_id)
        result: list[ParticipantPresence] = []
        for role in PartyRole:
            record: StoredAccess | None = records.get(role)
            if record is None:
                result.append(ParticipantPresence(role=role, status="waiting"))
                continue
            status = (
                "connected"
                if now - record.last_seen_at <= timedelta(seconds=15)
                else "offline"
            )
            result.append(
                ParticipantPresence(
                    role=role, status=status, last_seen_at=record.last_seen_at
                )
            )
        return result

    def close(self) -> None:
        self._repository.close()
