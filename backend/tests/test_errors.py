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
