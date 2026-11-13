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
