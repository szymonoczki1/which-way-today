"""Checking a route without saving it: GET /routes/comparison and /routes/recommendation."""

from datetime import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.clients.schemas import RouteResult, WeatherResult
from app.services import comparison_service, recommendation_service

OSRM = "app.services.comparison_service.osrm.get_route"
WEATHER = "app.services.comparison_service.open_meteo.get_current_weather"
TRANSIT = "app.services.comparison_service.transitous.plan"
FORECAST = "app.services.recommendation_service.open_meteo.get_forecast_at"

WEATHER_OK = WeatherResult(temperature_c=10, precipitation_mm=0, wind_speed_kmh=10, weather_code=1)
ROUTE = RouteResult(distance_m=3000, duration_s=600, geometry=[[54.35, 18.64], [54.37, 18.61]])

PARAMS = {
    "origin_lat": 54.3557,
    "origin_lon": 18.6440,
    "destination_lat": 54.3713,
    "destination_lon": 18.6123,
}


@pytest.fixture(autouse=True)
def no_ai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommendation_service, "_ai_settings", lambda: (None, "m"))


class TestRouteComparison:
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_compares_an_unsaved_route(
        self, _route: MagicMock, _weather: MagicMock, client: TestClient
    ) -> None:
        response = client.get("/routes/comparison", params=PARAMS)

        assert response.status_code == 200
        body = response.json()
        assert body["trip_id"] is None
        assert [o["mode"] for o in body["options"]] == ["walk", "bike", "transit", "car"]
        assert body["weather"]["weather_code"] == 1

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_does_not_save_anything(
        self, _route: MagicMock, _weather: MagicMock, client: TestClient
    ) -> None:
        client.get("/routes/comparison", params=PARAMS)
        client.get("/routes/recommendation", params=PARAMS)

        assert client.get("/trips").json() == []

    @patch(TRANSIT, return_value=None)
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_uses_the_optional_departure_time(
        self, _r: MagicMock, _w: MagicMock, plan: MagicMock, client: TestClient
    ) -> None:
        client.get("/routes/comparison", params={**PARAMS, "departure_time": "08:00"})

        local = plan.call_args.kwargs["depart_at"].astimezone(comparison_service.LOCAL_TZ)
        assert (local.hour, local.minute) == (8, 0)

    @pytest.mark.parametrize(
        "params",
        [
            {**PARAMS, "origin_lat": 999},
            {**PARAMS, "destination_lon": -181},
            {**PARAMS, "departure_time": "25:00"},
            {k: v for k, v in PARAMS.items() if k != "destination_lat"},
            {},
        ],
    )
    @patch(OSRM)
    def test_rejects_invalid_input(
        self, mock_route: MagicMock, client: TestClient, params: dict
    ) -> None:
        response = client.get("/routes/comparison", params=params)

        assert response.status_code == 422
        mock_route.assert_not_called()


class TestRouteRecommendation:
    @patch(FORECAST, return_value=None)
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_recommends_for_an_unsaved_route(
        self, _route: MagicMock, _weather: MagicMock, _forecast: MagicMock, client: TestClient
    ) -> None:
        response = client.get(
            "/routes/recommendation", params={**PARAMS, "departure_time": "08:00"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["trip_id"] is None
        assert body["source"] == "rules"
        assert body["recommended_mode"] in {"walk", "bike", "transit", "car"}

    @patch(OSRM)
    def test_rejects_invalid_input(self, mock_route: MagicMock, client: TestClient) -> None:
        response = client.get("/routes/recommendation", params={**PARAMS, "origin_lat": "north"})

        assert response.status_code == 422
        mock_route.assert_not_called()


class TestCheckThenSave:
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_saving_a_checked_route_reuses_the_computation(
        self, mock_route: MagicMock, _w: MagicMock, client: TestClient
    ) -> None:
        client.get("/routes/comparison", params={**PARAMS, "departure_time": "08:00"})
        trip = client.post(
            "/trips",
            json={
                **PARAMS,
                "name": "Checked first",
                "origin_address": "Gdańsk Główny",
                "destination_address": "Politechnika",
                "usual_departure_time": "08:00:00",
            },
        ).json()

        saved = client.get(f"/trips/{trip['id']}/comparison").json()

        assert mock_route.call_count == 3  # walk, bike, car once: not again after saving
        assert saved["trip_id"] == trip["id"]

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_a_route_never_gets_a_saved_trips_id_from_the_cache(
        self, _r: MagicMock, _w: MagicMock, client: TestClient
    ) -> None:
        trip = client.post(
            "/trips",
            json={**PARAMS, "name": "T", "origin_address": "A", "destination_address": "B"},
        ).json()
        client.get(f"/trips/{trip['id']}/comparison")

        unsaved = client.get("/routes/comparison", params=PARAMS).json()

        assert unsaved["trip_id"] is None


class TestDepartureTimeFormat:
    @pytest.mark.parametrize("value", ["08:00", "08:00:00", "23:59"])
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_accepts_hh_mm(
        self, _route: MagicMock, _weather: MagicMock, client: TestClient, value: str
    ) -> None:
        response = client.get("/routes/comparison", params={**PARAMS, "departure_time": value})

        assert response.status_code == 200

    @pytest.mark.parametrize("value", ["8:00", "0800", "", "08:00Z", "08:00+05:00", "08:00:00.5"])
    @patch(OSRM)
    def test_rejects_anything_else(
        self, mock_route: MagicMock, client: TestClient, value: str
    ) -> None:
        # Times are Gdańsk wall-clock; an offset would be silently ignored, so refuse it.
        response = client.get("/routes/comparison", params={**PARAMS, "departure_time": value})

        assert response.status_code == 422
        mock_route.assert_not_called()


class TestRecommendationUsesTheDepartureTime:
    @patch(FORECAST, return_value=None)
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_forecast_is_for_the_given_time(
        self, _route: MagicMock, _weather: MagicMock, forecast: MagicMock, client: TestClient
    ) -> None:
        client.get("/routes/recommendation", params={**PARAMS, "departure_time": "07:30"})

        assert forecast.call_args.args[2] == time(7, 30)


class TestCacheSeparatesDepartureTimes:
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, return_value=ROUTE)
    def test_same_route_at_another_time_is_computed_separately(
        self, mock_route: MagicMock, _weather: MagicMock, client: TestClient
    ) -> None:
        client.get("/routes/comparison", params={**PARAMS, "departure_time": "08:00"})
        client.get("/routes/comparison", params={**PARAMS, "departure_time": "17:00"})

        assert mock_route.call_count == 6
