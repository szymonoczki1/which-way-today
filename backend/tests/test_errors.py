import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ORIGIN = "http://localhost:5173"


def _client_with_failing_route() -> TestClient:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("unexpected")

    return TestClient(app, raise_server_exceptions=False)


def test_unhandled_error_returns_json_500_with_cors_headers() -> None:
    # Without a handler, Starlette's 500 is produced outside CORSMiddleware, so
    # the browser blocks it and the frontend wrongly reports "backend offline".
    response = _client_with_failing_route().get("/boom", headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers.get("access-control-allow-origin") == ORIGIN


def test_default_cors_allows_both_localhost_and_127() -> None:
    client = TestClient(create_app())

    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.get("/health", headers={"Origin": origin})
        assert response.headers.get("access-control-allow-origin") == origin


TRIP_JSON = (
    '{"name": "T", "origin_address": "A", "origin_lat": %s, "origin_lon": 18.64,'
    ' "destination_address": "B", "destination_lat": 54.37, "destination_lon": 18.61}'
)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_in_json_get_a_422_not_a_500(bad: str) -> None:
    # Python's JSON parser accepts NaN/Infinity. Pydantic rejects them, but the
    # default 422 echoes the input back, and NaN isn't valid JSON -> 500.
    client = TestClient(create_app(), raise_server_exceptions=False)

    response = client.post(
        "/trips", content=TRIP_JSON % bad, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    errors = response.json()["detail"]
    # Same shape as FastAPI's default, so the frontend can still name the field.
    assert errors[0]["loc"] == ["body", "origin_lat"]
    assert errors[0]["msg"]


def test_ordinary_validation_errors_keep_their_shape() -> None:
    client = TestClient(create_app())

    response = client.post("/trips", json={"name": ""})

    assert response.status_code == 422
    fields = {tuple(e["loc"]) for e in response.json()["detail"]}
    assert ("body", "origin_address") in fields
