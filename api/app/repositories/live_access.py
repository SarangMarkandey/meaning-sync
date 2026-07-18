from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from typing import Protocol

from sqlalchemy import DateTime, ForeignKey, String, create_engine, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.repositories.live_sessions import Base
from app.schemas.analysis import PartyRole


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AccessNotFound(Exception):
    pass


class AccessExpired(Exception):
    pass


class AccessRevoked(Exception):
    pass


class InvitationNotFound(Exception):
    pass


class InvitationExpired(Exception):
    pass


class InvitationUsed(Exception):
    pass


class InvitationRevoked(Exception):
    pass


@dataclass(frozen=True)
class StoredAccess:
    id: str
    session_id: str
    role: PartyRole
    expires_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class StoredInvitation:
    id: str
    session_id: str
    role: PartyRole
    expires_at: datetime


class LiveAccessRepository(Protocol):
    def create_access(
        self,
        *,
        access_id: str,
        session_id: str,
        role: PartyRole,
        token_hash: str,
        expires_at: datetime,
    ) -> StoredAccess: ...

    def authenticate(self, token_hash: str) -> StoredAccess: ...

    def create_invitation(
        self,
        *,
        invitation_id: str,
        session_id: str,
        role: PartyRole,
        invitation_hash: str,
        expires_at: datetime,
    ) -> StoredInvitation: ...

    def exchange_invitation(
        self,
        *,
        invitation_hash: str,
        access_id: str,
        access_hash: str,
        access_expires_at: datetime,
    ) -> StoredAccess: ...

    def revoke_invitations(self, session_id: str, role: PartyRole) -> None: ...

    def revoke_access(self, session_id: str, role: PartyRole) -> None: ...

    def presence(self, session_id: str) -> dict[PartyRole, StoredAccess]: ...

    def validate(self) -> None: ...

    def close(self) -> None: ...


@dataclass
class _MemoryAccess:
    id: str
    session_id: str
    role: PartyRole
    token_hash: str
    expires_at: datetime
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None


@dataclass
class _MemoryInvitation:
    id: str
    session_id: str
    role: PartyRole
    invitation_hash: str
    expires_at: datetime
    created_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None


class InMemoryLiveAccessRepository:
    def __init__(self) -> None:
        self._access: dict[str, _MemoryAccess] = {}
        self._invitations: dict[str, _MemoryInvitation] = {}
        self._lock = RLock()

    def create_access(self, **values) -> StoredAccess:
        now = _now()
        entry = _MemoryAccess(
            id=values["access_id"],
            session_id=values["session_id"],
            role=values["role"],
            token_hash=values["token_hash"],
            expires_at=values["expires_at"],
            created_at=now,
            last_seen_at=now,
        )
        with self._lock:
            self._access[entry.token_hash] = entry
        return self._stored(entry)

    def authenticate(self, token_hash: str) -> StoredAccess:
        with self._lock:
            entry = self._access.get(token_hash)
            if entry is None:
                raise AccessNotFound
            if entry.revoked_at is not None:
                raise AccessRevoked
            if entry.expires_at <= _now():
                raise AccessExpired
            entry.last_seen_at = _now()
            return self._stored(entry)

    def create_invitation(self, **values) -> StoredInvitation:
        entry = _MemoryInvitation(
            id=values["invitation_id"],
            session_id=values["session_id"],
            role=values["role"],
            invitation_hash=values["invitation_hash"],
            expires_at=values["expires_at"],
            created_at=_now(),
        )
        with self._lock:
            self.revoke_invitations(entry.session_id, entry.role)
            self._invitations[entry.invitation_hash] = entry
        return StoredInvitation(
            entry.id, entry.session_id, entry.role, entry.expires_at
        )

    def exchange_invitation(self, **values) -> StoredAccess:
        with self._lock:
            invitation = self._invitations.get(values["invitation_hash"])
            self._validate_invitation(invitation)
            assert invitation is not None
            invitation.used_at = _now()
            return self.create_access(
                access_id=values["access_id"],
                session_id=invitation.session_id,
                role=invitation.role,
                token_hash=values["access_hash"],
                expires_at=values["access_expires_at"],
            )

    def revoke_invitations(self, session_id: str, role: PartyRole) -> None:
        with self._lock:
            for entry in self._invitations.values():
                if (
                    entry.session_id == session_id
                    and entry.role == role
                    and entry.used_at is None
                    and entry.revoked_at is None
                ):
                    entry.revoked_at = _now()

    def revoke_access(self, session_id: str, role: PartyRole) -> None:
        with self._lock:
            for entry in self._access.values():
                if entry.session_id == session_id and entry.role == role:
                    entry.revoked_at = _now()

    def presence(self, session_id: str) -> dict[PartyRole, StoredAccess]:
        with self._lock:
            active = [
                entry
                for entry in self._access.values()
                if entry.session_id == session_id
                and entry.revoked_at is None
                and entry.expires_at > _now()
            ]
            return {
                role: self._stored(max(items, key=lambda item: item.last_seen_at))
                for role in PartyRole
                if (items := [entry for entry in active if entry.role == role])
            }

    def validate(self) -> None:
        return None

    def close(self) -> None:
        return None

    @staticmethod
    def _validate_invitation(entry: _MemoryInvitation | None) -> None:
        if entry is None:
            raise InvitationNotFound
        if entry.revoked_at is not None:
            raise InvitationRevoked
        if entry.used_at is not None:
            raise InvitationUsed
        if entry.expires_at <= _now():
            raise InvitationExpired

    @staticmethod
    def _stored(entry: _MemoryAccess) -> StoredAccess:
        return StoredAccess(
            entry.id,
            entry.session_id,
            entry.role,
            entry.expires_at,
            entry.last_seen_at,
        )


class LiveAccessRow(Base):
    __tablename__ = "live_access_credentials"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("live_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LiveInvitationRow(Base):
    __tablename__ = "live_session_invitations"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("live_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    invitation_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exchanged_access_id: Mapped[str | None] = mapped_column(String(120))


class SqlLiveAccessRepository:
    def __init__(self, database_url: str) -> None:
        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        )
        self._engine: Engine = create_engine(
            database_url, pool_pre_ping=True, connect_args=connect_args
        )
        self._factory = sessionmaker(
            self._engine, expire_on_commit=False, class_=Session
        )

    def create_access(self, **values) -> StoredAccess:
        now = _now()
        row = LiveAccessRow(
            id=values["access_id"],
            session_id=values["session_id"],
            role=values["role"],
            token_hash=values["token_hash"],
            expires_at=values["expires_at"],
            created_at=now,
            last_seen_at=now,
        )
        with self._factory.begin() as session:
            session.add(row)
        return self._stored(row)

    def authenticate(self, token_hash: str) -> StoredAccess:
        with self._factory.begin() as session:
            row = session.execute(
                select(LiveAccessRow).where(LiveAccessRow.token_hash == token_hash)
            ).scalar_one_or_none()
            self._validate_access(row)
            assert row is not None
            row.last_seen_at = _now()
            session.flush()
            return self._stored(row)

    def create_invitation(self, **values) -> StoredInvitation:
        now = _now()
        with self._factory.begin() as session:
            session.execute(
                update(LiveInvitationRow)
                .where(
                    LiveInvitationRow.session_id == values["session_id"],
                    LiveInvitationRow.role == values["role"].value,
                    LiveInvitationRow.used_at.is_(None),
                    LiveInvitationRow.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            row = LiveInvitationRow(
                id=values["invitation_id"],
                session_id=values["session_id"],
                role=values["role"],
                invitation_hash=values["invitation_hash"],
                expires_at=values["expires_at"],
                created_at=now,
            )
            session.add(row)
        return StoredInvitation(
            row.id, row.session_id, PartyRole(row.role), row.expires_at
        )

    def exchange_invitation(self, **values) -> StoredAccess:
        now = _now()
        with self._factory.begin() as session:
            row = session.execute(
                select(LiveInvitationRow).where(
                    LiveInvitationRow.invitation_hash == values["invitation_hash"]
                )
            ).scalar_one_or_none()
            self._validate_invitation(row)
            assert row is not None
            claimed = session.execute(
                update(LiveInvitationRow)
                .where(
                    LiveInvitationRow.id == row.id,
                    LiveInvitationRow.used_at.is_(None),
                    LiveInvitationRow.revoked_at.is_(None),
                    LiveInvitationRow.expires_at > now,
                )
                .values(used_at=now, exchanged_access_id=values["access_id"])
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                raise InvitationUsed
            access = LiveAccessRow(
                id=values["access_id"],
                session_id=row.session_id,
                role=row.role,
                token_hash=values["access_hash"],
                created_at=now,
                expires_at=values["access_expires_at"],
                last_seen_at=now,
            )
            session.add(access)
            session.flush()
            return self._stored(access)

    def revoke_invitations(self, session_id: str, role: PartyRole) -> None:
        with self._factory.begin() as session:
            session.execute(
                update(LiveInvitationRow)
                .where(
                    LiveInvitationRow.session_id == session_id,
                    LiveInvitationRow.role == role.value,
                    LiveInvitationRow.used_at.is_(None),
                    LiveInvitationRow.revoked_at.is_(None),
                )
                .values(revoked_at=_now())
            )

    def revoke_access(self, session_id: str, role: PartyRole) -> None:
        with self._factory.begin() as session:
            session.execute(
                update(LiveAccessRow)
                .where(
                    LiveAccessRow.session_id == session_id,
                    LiveAccessRow.role == role.value,
                    LiveAccessRow.revoked_at.is_(None),
                )
                .values(revoked_at=_now())
            )

    def presence(self, session_id: str) -> dict[PartyRole, StoredAccess]:
        with self._factory() as session:
            rows = session.execute(
                select(LiveAccessRow).where(
                    LiveAccessRow.session_id == session_id,
                    LiveAccessRow.revoked_at.is_(None),
                    LiveAccessRow.expires_at > _now(),
                )
            ).scalars()
            result: dict[PartyRole, StoredAccess] = {}
            for row in rows:
                role = PartyRole(row.role)
                stored = self._stored(row)
                if (
                    role not in result
                    or stored.last_seen_at > result[role].last_seen_at
                ):
                    result[role] = stored
            return result

    def validate(self) -> None:
        with self._engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            for table in ("live_access_credentials", "live_session_invitations"):
                if not self._engine.dialect.has_table(connection, table):
                    raise RuntimeError(
                        "MeaningSync database is not migrated; "
                        "run 'alembic upgrade head'"
                    )

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _validate_access(row: LiveAccessRow | None) -> None:
        if row is None:
            raise AccessNotFound
        if row.revoked_at is not None:
            raise AccessRevoked
        if _utc(row.expires_at) <= _now():
            raise AccessExpired

    @staticmethod
    def _validate_invitation(row: LiveInvitationRow | None) -> None:
        if row is None:
            raise InvitationNotFound
        if row.revoked_at is not None:
            raise InvitationRevoked
        if row.used_at is not None:
            raise InvitationUsed
        if _utc(row.expires_at) <= _now():
            raise InvitationExpired

    @staticmethod
    def _stored(row: LiveAccessRow) -> StoredAccess:
        return StoredAccess(
            row.id,
            row.session_id,
            PartyRole(row.role),
            _utc(row.expires_at),
            _utc(row.last_seen_at),
        )
