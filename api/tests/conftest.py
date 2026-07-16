import asyncio

import pytest

from app.services.sessions import SessionService


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def service() -> SessionService:
    return SessionService()


@pytest.fixture
def discussion_session(service: SessionService) -> str:
    session = service.create_demo()
    service.submit_consent(session.id, "hirer", True)
    service.submit_consent(session.id, "worker", True)
    return session.id


@pytest.fixture
def clarification_session(service: SessionService, discussion_session: str) -> str:
    asyncio.run(service.analyze(discussion_session))
    service.begin_clarification(discussion_session)
    return discussion_session
