import time as clock
from datetime import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.clients.open_meteo import ForecastResult
from app.clients.schemas import WeatherResult
from app.models import Trip
from app.schemas import ModeOption, TripComparison
from app.services import recommendation_service
from app.services.recommendation_service import recommend_trip, rule_based_recommendation

SVC = "app.services.recommendation_service"

DRY = WeatherResult(temperature_c=12, precipitation_mm=0, wind_speed_kmh=10, weather_code=1)
RAIN = WeatherResult(temperature_c=6, precipitation_mm=1.2, wind_speed_kmh=15, weather_code=63)
WINDY = WeatherResult(temperature_c=8, precipitation_mm=0, wind_speed_kmh=45, weather_code=3)
FREEZING = WeatherResult(temperature_c=-3, precipitation_mm=0, wind_speed_kmh=5, weather_code=0)


def _opt(mode: str, minutes: float, *, km: float = 3.0, co2: int = 0) -> ModeOption:
    return ModeOption(
        mode=mode,  # type: ignore[arg-type]
        duration_min=minutes,
        distance_km=km,
        cost_pln=0,
        co2_g=co2,
        is_estimate=mode == "transit",
    )


def _options(walk: float, bike: float, transit: float, car: float) -> list[ModeOption]:
    return [
        _opt("walk", walk),
        _opt("bike", bike),
        _opt("transit", transit, co2=170),
        _opt("car", car, co2=480),
    ]


class TestRules:
    def test_short_dry_trip_walks(self) -> None:
        rec = rule_based_recommendation(_options(15, 6, 14, 5), DRY, "now")
        assert rec.recommended_mode == "walk"

    def test_medium_dry_trip_bikes(self) -> None:
        rec = rule_based_recommendation(_options(39, 11, 16, 6), DRY, "now")
        assert rec.recommended_mode == "bike"
        assert any("CO₂" in r for r in rec.reasons)

    @pytest.mark.parametrize("weather", [RAIN, WINDY, FREEZING])
    def test_bad_weather_rules_out_bike(self, weather: WeatherResult) -> None:
        rec = rule_based_recommendation(_options(39, 11, 16, 6), weather, "at 08:00")
        assert rec.recommended_mode == "transit"
        assert rec.reasons[0].lower().startswith("forecast at 08:00")

    def test_rain_rules_out_a_long_walk_but_not_a_very_short_one(self) -> None:
        long = rule_based_recommendation(_options(22, 8, 14, 5), RAIN, "now")
        tiny = rule_based_recommendation(_options(8, 4, 12, 4), RAIN, "now")
        assert long.recommended_mode != "walk"
        assert tiny.recommended_mode == "walk"

    def test_drives_when_transit_is_far_slower(self) -> None:
        rec = rule_based_recommendation(_options(180, 60, 70, 20), RAIN, "now")
        assert rec.recommended_mode == "car"

    def test_unknown_weather_still_recommends_and_says_so(self) -> None:
        rec = rule_based_recommendation(_options(39, 11, 16, 6), None, "now")
        assert rec.recommended_mode == "bike"
        assert any("weather" in r.lower() and "unavailable" in r.lower() for r in rec.reasons)

    def test_explains_why_greener_modes_were_skipped(self) -> None:
        rec = rule_based_recommendation(_options(39, 11, 16, 6), RAIN, "now")
        text = " ".join(rec.reasons).lower()
        assert "cycling" in text or "bike" in text
        assert set(rec.unsuitable) == {"walk", "bike"}
        assert rec.unsuitable["bike"] == "Too wet for cycling."


TRIP = Trip(
    id=1,
    name="Home -> Uni",
    origin_address="Secret Street 1",
    origin_lat=54.355,
    origin_lon=18.646,
    destination_address="Hidden Road 2",
    destination_lat=54.371,
    destination_lon=18.613,
    usual_departure_time=time(8, 0),
)


def _comparison(weather: WeatherResult | None = DRY) -> TripComparison:
    return TripComparison(trip_id=1, weather=weather, options=_options(39, 11, 16, 6))


@pytest.fixture
def no_ai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommendation_service, "_ai_settings", lambda: (None, "m"))


@pytest.fixture
def ai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(recommendation_service, "_ai_settings", lambda: ("sk-test", "m"))


class TestRecommendTrip:
    @patch(f"{SVC}.openai_client.complete_json")
    @patch(f"{SVC}.open_meteo.get_forecast_at")
    @patch(f"{SVC}.get_shared_comparison")
    def test_uses_departure_forecast_and_rules_without_key(
        self, compare: MagicMock, forecast: MagicMock, llm: MagicMock, no_ai_key: None
    ) -> None:
        compare.return_value = _comparison(weather=DRY)
        forecast.return_value = ForecastResult(
            weather=RAIN, time="2026-11-14T08:00", departure_day="tomorrow"
        )

        rec = recommend_trip(TRIP)

        assert rec.source == "rules"
        assert rec.recommended_mode == "transit"  # rain at 08:00 beats dry "now"
        # Says *which* 08:00, so "this morning" isn't implied the evening before.
        assert rec.reasons[0].startswith("Forecast tomorrow at 08:00")
        assert rec.weather is not None
        assert rec.weather.is_forecast is True
        assert rec.weather.time == "2026-11-14T08:00"
        llm.assert_not_called()

    @patch(f"{SVC}.open_meteo.get_forecast_at")
    @patch(f"{SVC}.get_shared_comparison")
    def test_falls_back_to_current_weather_when_forecast_fails(
        self, compare: MagicMock, forecast: MagicMock, no_ai_key: None
    ) -> None:
        compare.return_value = _comparison(weather=DRY)
        forecast.return_value = None

        rec = recommend_trip(TRIP)

        assert rec.weather is not None
        assert rec.weather.is_forecast is False
        assert rec.recommended_mode == "bike"

    @patch(f"{SVC}.open_meteo.get_forecast_at")
    @patch(f"{SVC}.get_shared_comparison")
    def test_no_departure_time_skips_forecast(
        self, compare: MagicMock, forecast: MagicMock, no_ai_key: None
    ) -> None:
        compare.return_value = _comparison(weather=None)

        rec = recommend_trip(TRIP.model_copy(update={"usual_departure_time": None}))

        forecast.assert_not_called()
        assert rec.weather is None
        assert rec.source == "rules"

    @patch(f"{SVC}.openai_client.complete_json")
    @patch(f"{SVC}.open_meteo.get_forecast_at", return_value=None)
    @patch(f"{SVC}.get_shared_comparison")
    def test_uses_ai_answer_when_valid(
        self, compare: MagicMock, _f: MagicMock, llm: MagicMock, ai_key: None
    ) -> None:
        compare.return_value = _comparison()
        llm.return_value = {
            "recommended_mode": "transit",
            "reasons": ["Dry now, but transit is nearly as fast.", "Saves 310 g CO₂."],
        }

        rec = recommend_trip(TRIP)

        assert rec.source == "ai"
        assert rec.recommended_mode == "transit"
        assert rec.reasons[0] == "Dry now, but transit is nearly as fast."
        # Headline is built from the chosen mode, so it can never contradict it.
        assert rec.headline == "Take public transport: ~16 min"
        # The model is grounded in the same facts the rules use...
        user_prompt = llm.call_args.args[1]
        assert '"bike"' in user_prompt and "11" in user_prompt
        assert "rule_based_suggestion" in user_prompt
        assert "unsuitable_modes" in user_prompt
        # ...and never sees the user's trip name or addresses.
        for private in ("Home -> Uni", "Secret Street 1", "Hidden Road 2"):
            assert private not in user_prompt

    @pytest.mark.parametrize(
        "bad",
        [
            None,  # client failure / timeout
            {"recommended_mode": "teleport", "reasons": ["y"]},
            {"recommended_mode": "walk", "reasons": ["y"]},  # 39 min: rules ruled it out
            {"recommended_mode": "bike", "reasons": []},
            {"recommended_mode": "bike", "reasons": ["   "]},
            {"recommended_mode": "bike", "reasons": "not a list"},
            {"recommended_mode": "bike", "reasons": ["x" * 500]},
            {"reasons": ["no mode"]},
        ],
    )
    @patch(f"{SVC}.openai_client.complete_json")
    @patch(f"{SVC}.open_meteo.get_forecast_at", return_value=None)
    @patch(f"{SVC}.get_shared_comparison")
    def test_falls_back_to_rules_on_invalid_ai_answer(
        self, compare: MagicMock, _f: MagicMock, llm: MagicMock, bad: object, ai_key: None
    ) -> None:
        compare.return_value = _comparison()
        llm.return_value = bad

        rec = recommend_trip(TRIP)

        assert rec.source == "rules"
        assert rec.recommended_mode == "bike"

    @patch(f"{SVC}.openai_client.complete_json")
    @patch(f"{SVC}.open_meteo.get_forecast_at", return_value=None)
    @patch(f"{SVC}.get_shared_comparison")
    def test_ai_cannot_pick_a_mode_the_weather_rules_out(
        self, compare: MagicMock, _f: MagicMock, llm: MagicMock, ai_key: None
    ) -> None:
        compare.return_value = _comparison(weather=WINDY)  # 45 km/h: no cycling
        llm.return_value = {"recommended_mode": "bike", "reasons": ["Bike, it's fine."]}

        rec = recommend_trip(TRIP)

        assert rec.source == "rules"
        assert rec.recommended_mode == "transit"

    @patch(f"{SVC}.openai_client.complete_json", side_effect=RuntimeError("boom"))
    @patch(f"{SVC}.open_meteo.get_forecast_at", side_effect=RuntimeError("boom"))
    @patch(f"{SVC}.get_shared_comparison")
    def test_unexpected_errors_fall_back_instead_of_500(
        self, compare: MagicMock, _f: MagicMock, _llm: MagicMock, ai_key: None
    ) -> None:
        compare.return_value = _comparison(weather=DRY)

        rec = recommend_trip(TRIP)

        assert rec.source == "rules"
        assert rec.weather is not None and rec.weather.is_forecast is False

    @patch(f"{SVC}.open_meteo.get_forecast_at")
    @patch(f"{SVC}.get_shared_comparison")
    def test_slow_forecast_does_not_exceed_the_deadline(
        self, compare: MagicMock, forecast: MagicMock, no_ai_key: None
    ) -> None:
        compare.return_value = _comparison(weather=DRY)

        def slow(*_: object) -> ForecastResult:
            clock.sleep(0.5)
            return ForecastResult(weather=RAIN, time="2026-11-14T08:00", departure_day="today")

        forecast.side_effect = slow

        started = clock.monotonic()
        rec = recommend_trip(TRIP, deadline_s=0.05)
        elapsed = clock.monotonic() - started

        assert elapsed < 0.3
        assert rec.weather is not None and rec.weather.is_forecast is False


VALID_TRIP = {
    "name": "Home -> Uni",
    "origin_address": "A",
    "origin_lat": 54.355,
    "origin_lon": 18.646,
    "destination_address": "B",
    "destination_lat": 54.371,
    "destination_lon": 18.613,
    "usual_departure_time": "08:00:00",
}


class TestRecommendationEndpoint:
    @patch(f"{SVC}.open_meteo.get_forecast_at", return_value=None)
    @patch(f"{SVC}.get_shared_comparison")
    def test_returns_recommendation(
        self, compare: MagicMock, _f: MagicMock, client: TestClient, no_ai_key: None
    ) -> None:
        compare.return_value = _comparison()
        trip_id = client.post("/trips", json=VALID_TRIP).json()["id"]

        response = client.get(f"/trips/{trip_id}/recommendation")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {
            "trip_id",
            "source",
            "recommended_mode",
            "headline",
            "reasons",
            "weather",
        }
        assert body["trip_id"] == trip_id
        assert body["source"] == "rules"
        assert body["weather"]["is_forecast"] is False

    @patch(f"{SVC}.get_shared_comparison")
    def test_returns_404_for_missing_trip(self, compare: MagicMock, client: TestClient) -> None:
        response = client.get("/trips/999/recommendation")

        assert response.status_code == 404
        compare.assert_not_called()
