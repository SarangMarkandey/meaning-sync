from __future__ import annotations

from contextlib import AbstractContextManager
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Protocol

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    create_engine,
    select,
    text,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.schemas.persistence import PersistedLiveSessionState


class RepositorySessionNotFound(Exception):
    pass


class RepositorySessionExpired(Exception):
    pass


class RepositoryConflict(Exception):
    pass


class RepositoryStateInvalid(Exception):
    pass


@dataclass(frozen=True)
class StoredLiveSession:
    state: PersistedLiveSessionState
    revision: int
    expires_at: datetime


@dataclass
class LiveSessionTransaction:
    state: PersistedLiveSessionState
    revision: int
    committed_revision: int | None = None


class LiveSessionRepository(Protocol):
    def create(self, state: PersistedLiveSessionState) -> StoredLiveSession: ...

    def load(self, session_id: str) -> StoredLiveSession: ...

    def transaction(
        self, session_id: str, *, expected_revision: int | None = None
    ) -> AbstractContextManager[LiveSessionTransaction]: ...

    def validate(self) -> None: ...

    def close(self) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _validated_copy(state: PersistedLiveSessionState) -> PersistedLiveSessionState:
    try:
        return PersistedLiveSessionState.model_validate(
            state.model_dump(mode="json", round_trip=True)
        )
    except Exception as exc:
        raise RepositoryStateInvalid("stored Live session state is invalid") from exc


@dataclass
class _MemoryEntry:
    state: PersistedLiveSessionState
    revision: int
    expires_at: datetime


class _MemoryTransaction(AbstractContextManager[LiveSessionTransaction]):
    def __init__(
        self,
        repository: InMemoryLiveSessionRepository,
        session_id: str,
        expected_revision: int | None,
    ) -> None:
        self._repository = repository
        self._session_id = session_id
        self._expected_revision = expected_revision
        self.transaction: LiveSessionTransaction | None = None
        self._original_state: PersistedLiveSessionState | None = None

    def __enter__(self) -> LiveSessionTransaction:
        stored = self._repository.load(self._session_id)
        if (
            self._expected_revision is not None
            and stored.revision != self._expected_revision
        ):
            raise RepositoryConflict("the Live session revision changed")
        self.transaction = LiveSessionTransaction(stored.state, stored.revision)
        self._original_state = _validated_copy(stored.state)
        return self.transaction

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None:
            return False
        if self.transaction is None:
            raise RuntimeError("Live session transaction was not entered")
        if self.transaction.state == self._original_state:
            self.transaction.committed_revision = self.transaction.revision
            return False
        committed = self._repository._save(
            self._session_id,
            self.transaction.state,
            expected_revision=self.transaction.revision,
        )
        self.transaction.committed_revision = committed.revision
        return False


class InMemoryLiveSessionRepository:
    """Explicit test repository; production wiring never falls back to it."""

    def __init__(self, *, ttl_hours: int = 24) -> None:
        self._ttl = timedelta(hours=ttl_hours)
        self._entries: dict[str, _MemoryEntry] = {}
        self._lock = RLock()

    def create(self, state: PersistedLiveSessionState) -> StoredLiveSession:
        now = _utcnow()
        entry = _MemoryEntry(_validated_copy(state), 1, now + self._ttl)
        with self._lock:
            if state.id in self._entries:
                raise RepositoryConflict("the Live session already exists")
            self._entries[state.id] = entry
        return StoredLiveSession(_validated_copy(entry.state), 1, entry.expires_at)

    def load(self, session_id: str) -> StoredLiveSession:
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is None:
                raise RepositorySessionNotFound(session_id)
            if entry.expires_at <= _utcnow():
                raise RepositorySessionExpired(session_id)
            return StoredLiveSession(
                _validated_copy(entry.state), entry.revision, entry.expires_at
            )

    def transaction(
        self, session_id: str, *, expected_revision: int | None = None
    ) -> AbstractContextManager[LiveSessionTransaction]:
        return _MemoryTransaction(self, session_id, expected_revision)

    def _save(
        self,
        session_id: str,
        state: PersistedLiveSessionState,
        *,
        expected_revision: int,
    ) -> StoredLiveSession:
        validated = _validated_copy(state)
        with self._lock:
            entry = self._entries.get(session_id)
            if entry is None:
                raise RepositorySessionNotFound(session_id)
            if entry.expires_at <= _utcnow():
                raise RepositorySessionExpired(session_id)
            if entry.revision != expected_revision:
                raise RepositoryConflict("the Live session revision changed")
            entry.state = validated
            entry.revision += 1
            return StoredLiveSession(
                _validated_copy(entry.state), entry.revision, entry.expires_at
            )

    def validate(self) -> None:
        return None

    def close(self) -> None:
        return None


class Base(DeclarativeBase):
    pass


class LiveSessionRow(Base):
    __tablename__ = "live_sessions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    state_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class _SqlTransaction(AbstractContextManager[LiveSessionTransaction]):
    def __init__(
        self,
        repository: SqlLiveSessionRepository,
        session_id: str,
        expected_revision: int | None,
    ) -> None:
        self._repository = repository
        self._session_id = session_id
        self._expected_revision = expected_revision
        self._session: Session | None = None
        self.transaction: LiveSessionTransaction | None = None
        self._original_state: PersistedLiveSessionState | None = None

    def __enter__(self) -> LiveSessionTransaction:
        self._session = self._repository._session_factory()
        self._session.begin()
        row = self._session.execute(
            select(LiveSessionRow).where(LiveSessionRow.id == self._session_id)
        ).scalar_one_or_none()
        if row is None:
            self._session.rollback()
            self._session.close()
            raise RepositorySessionNotFound(self._session_id)
        if _as_utc(row.expires_at) <= _utcnow():
            self._session.rollback()
            self._session.close()
            raise RepositorySessionExpired(self._session_id)
        if (
            self._expected_revision is not None
            and row.revision != self._expected_revision
        ):
            self._session.rollback()
            self._session.close()
            raise RepositoryConflict("the Live session revision changed")
        try:
            state = self._repository._decode(row.state_schema_version, row.state_json)
        except Exception:
            self._session.rollback()
            self._session.close()
            raise
        self.transaction = LiveSessionTransaction(state, row.revision)
        self._original_state = _validated_copy(state)
        return self.transaction

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if self._session is None:
            return False
        try:
            if exc_type is not None:
                self._session.rollback()
                return False
            if self.transaction is None:
                raise RuntimeError("Live session transaction was not entered")
            if self.transaction.state == self._original_state:
                self._session.rollback()
                self.transaction.committed_revision = self.transaction.revision
                return False
            state = _validated_copy(self.transaction.state)
            now = _utcnow()
            result = self._session.execute(
                update(LiveSessionRow)
                .where(
                    LiveSessionRow.id == self._session_id,
                    LiveSessionRow.revision == self.transaction.revision,
                    LiveSessionRow.expires_at > now,
                )
                .values(
                    state_schema_version=state.state_schema_version,
                    state_json=state.model_dump(mode="json", round_trip=True),
                    revision=self.transaction.revision + 1,
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                self._session.rollback()
                self._repository.load(self._session_id)
                raise RepositoryConflict("the Live session revision changed")
            self._session.commit()
            self.transaction.committed_revision = self.transaction.revision + 1
            return False
        finally:
            self._session.close()


class SqlLiveSessionRepository:
    def __init__(self, database_url: str, *, ttl_hours: int = 24) -> None:
        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        )
        self._engine: Engine = create_engine(
            database_url, pool_pre_ping=True, connect_args=connect_args
        )
        self._session_factory = sessionmaker(
            self._engine, expire_on_commit=False, class_=Session
        )
        self._ttl = timedelta(hours=ttl_hours)

    def create(self, state: PersistedLiveSessionState) -> StoredLiveSession:
        validated = _validated_copy(state)
        now = _utcnow()
        expires_at = now + self._ttl
        with self._session_factory.begin() as session:
            session.add(
                LiveSessionRow(
                    id=validated.id,
                    state_schema_version=validated.state_schema_version,
                    state_json=validated.model_dump(mode="json", round_trip=True),
                    revision=1,
                    created_at=validated.created_at,
                    updated_at=now,
                    expires_at=expires_at,
                )
            )
        return StoredLiveSession(_validated_copy(validated), 1, expires_at)

    def load(self, session_id: str) -> StoredLiveSession:
        with self._session_factory() as session:
            row = session.execute(
                select(LiveSessionRow).where(LiveSessionRow.id == session_id)
            ).scalar_one_or_none()
            if row is None:
                raise RepositorySessionNotFound(session_id)
            if _as_utc(row.expires_at) <= _utcnow():
                raise RepositorySessionExpired(session_id)
            return StoredLiveSession(
                self._decode(row.state_schema_version, row.state_json),
                row.revision,
                _as_utc(row.expires_at),
            )

    def transaction(
        self, session_id: str, *, expected_revision: int | None = None
    ) -> AbstractContextManager[LiveSessionTransaction]:
        return _SqlTransaction(self, session_id, expected_revision)

    def validate(self) -> None:
        try:
            with self._engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                if not self._engine.dialect.has_table(connection, "live_sessions"):
                    raise RuntimeError(
                        "MeaningSync database is not migrated; "
                        "run 'alembic upgrade head'"
                    )
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
            raise RuntimeError("MeaningSync database connection failed") from exc

    def close(self) -> None:
        self._engine.dispose()

    @staticmethod
    def _decode(schema_version: int, payload: dict) -> PersistedLiveSessionState:
        if schema_version != 1 or payload.get("state_schema_version") != 1:
            raise RepositoryStateInvalid("unsupported Live session state schema")
        try:
            return PersistedLiveSessionState.model_validate(deepcopy(payload))
        except Exception as exc:
            raise RepositoryStateInvalid(
                "stored Live session state is invalid"
            ) from exc
