import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.db import get_session
from app.main import app
from app.services import comparison_service


@pytest.fixture(name="session")
def session_fixture():
    # In-memory sqlite + StaticPool: one connection shared for the test's
    # lifetime, so the schema created here is visible to every request the
    # test client makes, instead of hitting the real dev whichway.db file.
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_shared_comparisons():
    # get_shared_comparison caches per trip; tests reuse ids and coordinates.
    comparison_service._shared.clear()
    yield
    comparison_service._shared.clear()


@pytest.fixture(autouse=True)
def _no_real_transitous(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    # Never call the real journey planner from tests; a test's own @patch
    # (applied after fixtures) overrides this when it needs a journey. The
    # client's own tests mock httpx instead, so they keep the real plan().
    if request.module.__name__.endswith("test_transitous"):
        return
    monkeypatch.setattr(comparison_service.transitous, "plan", lambda *a, **k: None)
