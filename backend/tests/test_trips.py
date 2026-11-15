import pytest
from fastapi.testclient import TestClient

VALID_TRIP = {
    "name": "Home -> Uni",
    "origin_address": "Gdansk Main Station",
    "origin_lat": 54.355,
    "origin_lon": 18.646,
    "destination_address": "Gdansk University of Technology",
    "destination_lat": 54.371,
    "destination_lon": 18.613,
    "usual_departure_time": "08:00:00",
}


def test_list_trips_empty(client: TestClient) -> None:
    response = client.get("/trips")

    assert response.status_code == 200
    assert response.json() == []


def test_create_trip(client: TestClient) -> None:
    response = client.post("/trips", json=VALID_TRIP)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["name"] == VALID_TRIP["name"]
    assert body["usual_departure_time"] == "08:00:00"


@pytest.mark.parametrize("field", ["origin_address", "destination_address"])
def test_create_trip_rejects_overlong_address(client: TestClient, field: str) -> None:
    # Same 200-character limit as GET /geocode and the form inputs.
    response = client.post("/trips", json={**VALID_TRIP, field: "x" * 201})

    assert response.status_code == 422


def test_create_trip_accepts_a_200_character_address(client: TestClient) -> None:
    response = client.post("/trips", json={**VALID_TRIP, "origin_address": "x" * 200})

    assert response.status_code == 201


def test_create_trip_rejects_invalid_latitude(client: TestClient) -> None:
    invalid = {**VALID_TRIP, "origin_lat": 999}

    response = client.post("/trips", json=invalid)

    assert response.status_code == 422


def test_get_trip(client: TestClient) -> None:
    created = client.post("/trips", json=VALID_TRIP).json()

    response = client.get(f"/trips/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_trip_not_found(client: TestClient) -> None:
    response = client.get("/trips/999")

    assert response.status_code == 404


def test_update_trip(client: TestClient) -> None:
    created = client.post("/trips", json=VALID_TRIP).json()
    updated_payload = {**VALID_TRIP, "name": "Home -> Office"}

    response = client.put(f"/trips/{created['id']}", json=updated_payload)

    assert response.status_code == 200
    assert response.json()["name"] == "Home -> Office"
    assert response.json()["id"] == created["id"]


def test_update_trip_not_found(client: TestClient) -> None:
    response = client.put("/trips/999", json=VALID_TRIP)

    assert response.status_code == 404


def test_delete_trip(client: TestClient) -> None:
    created = client.post("/trips", json=VALID_TRIP).json()

    delete_response = client.delete(f"/trips/{created['id']}")
    get_response = client.get(f"/trips/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404


def test_delete_trip_not_found(client: TestClient) -> None:
    response = client.delete("/trips/999")

    assert response.status_code == 404
