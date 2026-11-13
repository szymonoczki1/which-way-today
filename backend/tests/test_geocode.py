from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.clients.nominatim import GeocodingUnavailableError
from app.clients.schemas import GeocodeResult

GEOCODE = "app.services.geocoding_service.nominatim.geocode"


@patch(GEOCODE)
def test_geocode_returns_location(mock_geocode: MagicMock, client: TestClient) -> None:
    mock_geocode.return_value = GeocodeResult(lat=54.35, lon=18.64, display_name="Gdansk, PL")

    response = client.get("/geocode", params={"q": "Gdansk"})

    assert response.status_code == 200
    assert response.json() == {"lat": 54.35, "lon": 18.64, "display_name": "Gdansk, PL"}
    mock_geocode.assert_called_once_with("Gdansk")


@patch(GEOCODE)
def test_geocode_returns_404_when_address_not_found(
    mock_geocode: MagicMock, client: TestClient
) -> None:
    mock_geocode.return_value = None

    response = client.get("/geocode", params={"q": "nowhere xyz123"})

    assert response.status_code == 404


@patch(GEOCODE)
def test_geocode_returns_503_when_upstream_unavailable(
    mock_geocode: MagicMock, client: TestClient
) -> None:
    mock_geocode.side_effect = GeocodingUnavailableError("Nominatim down")

    response = client.get("/geocode", params={"q": "Gdansk"})

    assert response.status_code == 503


@patch(GEOCODE)
def test_geocode_rejects_blank_query(mock_geocode: MagicMock, client: TestClient) -> None:
    missing = client.get("/geocode")
    blank = client.get("/geocode", params={"q": "   "})

    assert missing.status_code == 422
    assert blank.status_code == 422
    mock_geocode.assert_not_called()
