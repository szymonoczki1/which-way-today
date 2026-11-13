import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.clients.schemas import RouteResult, WeatherResult
from app.models import Trip
from app.services import comparison_service
from app.services.comparison_service import compare_trip

OSRM = "app.services.comparison_service.osrm.get_route"
WEATHER = "app.services.comparison_service.open_meteo.get_current_weather"

TRIP = Trip(
    id=1,
    name="Home -> Uni",
    origin_address="Gdansk Main Station",
    origin_lat=54.355,
    origin_lon=18.646,
    destination_address="Gdansk University of Technology",
    destination_lat=54.371,
    destination_lon=18.613,
)

WEATHER_OK = WeatherResult(
    temperature_c=5.0, precipitation_mm=2.0, wind_speed_kmh=20.0, weather_code=61
)

# Distinct durations per profile so we can tell which route fed which mode.
ROUTES = {
    "walking": RouteResult(distance_m=3000.0, duration_s=2400.0, geometry=[[54.355, 18.646]]),
    "cycling": RouteResult(distance_m=3200.0, duration_s=720.0, geometry=[[54.355, 18.646]]),
    "driving": RouteResult(distance_m=4000.0, duration_s=480.0, geometry=[[54.355, 18.646]]),
}


def _fake_route(*args: object) -> RouteResult | None:
    return ROUTES[args[4]]  # type: ignore[index]


def _by_mode(result: comparison_service.TripComparison) -> dict:
    return {option.mode: option for option in result.options}


class TestCompareTrip:
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_uses_routes_for_each_mode(self, *_: object) -> None:
        result = compare_trip(TRIP)

        assert [o.mode for o in result.options] == ["walk", "bike", "transit", "car"]
        modes = _by_mode(result)
        assert modes["walk"].duration_min == 40.0
        assert modes["walk"].distance_km == 3.0
        assert modes["bike"].duration_min == 12.0
        assert modes["car"].duration_min == 8.0
        assert modes["car"].distance_km == 4.0
        assert not any(o.is_estimate for o in (modes["walk"], modes["bike"], modes["car"]))
        assert result.weather == WEATHER_OK
        assert result.trip_id == 1

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_cost_and_co2(self, *_: object) -> None:
        modes = _by_mode(compare_trip(TRIP))

        for green in ("walk", "bike"):
            assert modes[green].cost_pln == 0
            assert modes[green].co2_g == 0
        assert modes["car"].cost_pln == round(4.0 * comparison_service.CAR_COST_PLN_PER_KM, 2)
        assert modes["car"].co2_g == round(4.0 * comparison_service.CAR_CO2_G_PER_KM)
        assert modes["transit"].cost_pln == comparison_service.TRANSIT_TICKET_PLN
        assert 0 < modes["transit"].co2_g < modes["car"].co2_g

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_transit_is_always_estimate_based_on_driving_distance(self, *_: object) -> None:
        transit = _by_mode(compare_trip(TRIP))["transit"]

        assert transit.is_estimate
        assert transit.distance_km == 4.0
        expected = 4.0 / comparison_service.TRANSIT_SPEED_KMH * 60
        expected += comparison_service.TRANSIT_OVERHEAD_MIN
        assert transit.duration_min == round(expected, 1)

    @patch(WEATHER, return_value=None)
    @patch(OSRM, return_value=None)
    def test_falls_back_to_estimates_when_every_upstream_fails(self, *_: object) -> None:
        result = compare_trip(TRIP)

        assert result.weather is None
        assert len(result.options) == 4
        for option in result.options:
            assert option.is_estimate
            assert option.distance_km > 0
            assert option.duration_min > 0
        modes = _by_mode(result)
        assert modes["walk"].duration_min > modes["bike"].duration_min > 0

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM)
    def test_only_failed_mode_is_estimated(self, mock_route, *_: object) -> None:
        mock_route.side_effect = lambda *a: None if a[4] == "cycling" else ROUTES[a[4]]

        modes = _by_mode(compare_trip(TRIP))

        assert modes["bike"].is_estimate
        assert not modes["walk"].is_estimate
        assert not modes["car"].is_estimate

    @patch(WEATHER, side_effect=RuntimeError("unexpected"))
    @patch(OSRM, side_effect=_fake_route)
    def test_unexpected_client_exception_does_not_propagate(self, *_: object) -> None:
        result = compare_trip(TRIP)

        assert result.weather is None
        assert len(result.options) == 4

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM)
    def test_slow_upstream_does_not_exceed_deadline(self, mock_route, *_: object) -> None:
        def slow_walking(*a: object) -> RouteResult | None:
            if a[4] == "walking":
                time.sleep(0.3)
            return ROUTES[a[4]]  # type: ignore[index]

        mock_route.side_effect = slow_walking

        started = time.monotonic()
        modes = _by_mode(compare_trip(TRIP, deadline_s=0.05))
        elapsed = time.monotonic() - started

        assert elapsed < 0.25
        assert modes["walk"].is_estimate
        assert not modes["car"].is_estimate

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_upstream_calls_run_concurrently(self, mock_route, *_: object) -> None:
        def slow(*a: object) -> RouteResult | None:
            time.sleep(0.3)
            return ROUTES[a[4]]  # type: ignore[index]

        mock_route.side_effect = slow

        started = time.monotonic()
        modes = _by_mode(compare_trip(TRIP))
        elapsed = time.monotonic() - started

        # 3 routes x 0.3 s sequentially would be 0.9 s.
        assert elapsed < 0.85
        assert not modes["walk"].is_estimate

    @patch(WEATHER, return_value=None)
    @patch(OSRM, return_value=None)
    def test_identical_origin_and_destination(self, *_: object) -> None:
        trip = TRIP.model_copy(update={"destination_lat": 54.355, "destination_lon": 18.646})

        result = compare_trip(trip)

        for option in result.options:
            assert option.distance_km == 0
            assert option.co2_g == 0
        transit = _by_mode(result)["transit"]
        # You still pay the fare and wait for the tram, even for a ~0 km hop.
        assert transit.cost_pln == comparison_service.TRANSIT_TICKET_PLN
        assert transit.duration_min == comparison_service.TRANSIT_OVERHEAD_MIN

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM)
    def test_transit_uses_estimated_car_distance_when_driving_fails(
        self, mock_route: MagicMock, *_: object
    ) -> None:
        mock_route.side_effect = lambda *a: None if a[4] == "driving" else ROUTES[a[4]]

        modes = _by_mode(compare_trip(TRIP))

        assert modes["car"].is_estimate
        assert not modes["walk"].is_estimate
        assert modes["transit"].distance_km == modes["car"].distance_km
        crow = comparison_service._haversine_km(54.355, 18.646, 54.371, 18.613)
        assert modes["car"].distance_km == round(crow * comparison_service.DETOUR_FACTOR, 2)

    @patch(WEATHER)
    @patch(OSRM, side_effect=_fake_route)
    def test_slow_weather_returns_null_weather(
        self, _route: MagicMock, mock_weather: MagicMock
    ) -> None:
        def slow_weather(*_: object) -> WeatherResult:
            time.sleep(0.3)
            return WEATHER_OK

        mock_weather.side_effect = slow_weather

        result = compare_trip(TRIP, deadline_s=0.05)

        assert result.weather is None
        assert len(result.options) == 4

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM)
    def test_zero_deadline_falls_back_without_raising(
        self, mock_route: MagicMock, *_: object
    ) -> None:
        # Futures still queued at the deadline get cancelled; that must not 500.
        mock_route.side_effect = lambda *a: time.sleep(0.2) or ROUTES[a[4]]

        result = compare_trip(TRIP, deadline_s=0)

        assert all(o.is_estimate for o in result.options)

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_includes_route_geometry_for_live_routes_only(self, *_: object) -> None:
        modes = _by_mode(compare_trip(TRIP))

        assert modes["walk"].geometry == ROUTES["walking"].geometry
        assert modes["car"].geometry == ROUTES["driving"].geometry
        assert modes["transit"].geometry is None

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM)
    def test_cost_and_co2_consistent_with_rounded_distance(
        self, mock_route: MagicMock, *_: object
    ) -> None:
        tiny = RouteResult(distance_m=3.0, duration_s=1.0, geometry=[])
        mock_route.side_effect = lambda *a: tiny

        car = _by_mode(compare_trip(TRIP))["car"]

        assert car.distance_km == 0.0
        assert car.co2_g == 0
        assert car.cost_pln == 0.0


class TestSharedComparison:
    @pytest.fixture(autouse=True)
    def _clear(self) -> None:
        comparison_service._shared.clear()

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM)
    def test_concurrent_requests_share_one_computation(self, mock_route, *_: object) -> None:
        # /comparison and /recommendation arrive together for the same trip view.
        def slow(*a: object) -> RouteResult | None:
            time.sleep(0.2)
            return ROUTES[a[4]]  # type: ignore[index]

        mock_route.side_effect = slow

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(comparison_service.get_shared_comparison, [TRIP, TRIP])

        assert mock_route.call_count == 3  # one walk/bike/car set, not two
        assert first == second

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_recomputes_after_the_ttl(
        self, mock_route: MagicMock, _weather: MagicMock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(comparison_service, "SHARED_TTL_S", 0.0)

        comparison_service.get_shared_comparison(TRIP)
        comparison_service.get_shared_comparison(TRIP)

        assert mock_route.call_count == 6

    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_reused_id_with_new_coordinates_is_not_served_from_cache(
        self, mock_route, *_: object
    ) -> None:
        moved = TRIP.model_copy(update={"destination_lat": 54.5})

        comparison_service.get_shared_comparison(TRIP)
        comparison_service.get_shared_comparison(moved)

        assert mock_route.call_count == 6


VALID_TRIP = {
    "name": "Home -> Uni",
    "origin_address": "Gdansk Main Station",
    "origin_lat": 54.355,
    "origin_lon": 18.646,
    "destination_address": "Gdansk University of Technology",
    "destination_lat": 54.371,
    "destination_lon": 18.613,
}


class TestComparisonEndpoint:
    @patch(WEATHER, return_value=WEATHER_OK)
    @patch(OSRM, side_effect=_fake_route)
    def test_returns_comparison(
        self, mock_route: MagicMock, mock_weather: MagicMock, client: TestClient
    ) -> None:
        trip_id = client.post("/trips", json=VALID_TRIP).json()["id"]

        response = client.get(f"/trips/{trip_id}/comparison")

        assert response.status_code == 200
        body = response.json()
        assert body["trip_id"] == trip_id
        assert body["weather"]["weather_code"] == 61
        assert {o["mode"] for o in body["options"]} == {"walk", "bike", "transit", "car"}
        assert set(body["options"][0]) == {
            "mode",
            "duration_min",
            "distance_km",
            "cost_pln",
            "co2_g",
            "is_estimate",
            "geometry",
        }

    @patch(WEATHER, return_value=None)
    @patch(OSRM, return_value=None)
    def test_returns_200_with_null_weather_when_upstreams_down(
        self, mock_route: MagicMock, mock_weather: MagicMock, client: TestClient
    ) -> None:
        trip_id = client.post("/trips", json=VALID_TRIP).json()["id"]

        response = client.get(f"/trips/{trip_id}/comparison")

        assert response.status_code == 200
        assert response.json()["weather"] is None

    @patch(WEATHER)
    @patch(OSRM)
    def test_returns_404_for_missing_trip(
        self, mock_route: MagicMock, mock_weather: MagicMock, client: TestClient
    ) -> None:
        response = client.get("/trips/999/comparison")

        assert response.status_code == 404
        mock_route.assert_not_called()
        mock_weather.assert_not_called()
