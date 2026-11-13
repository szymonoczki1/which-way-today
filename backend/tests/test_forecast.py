from datetime import UTC, datetime, time
from unittest.mock import MagicMock, patch

import httpx

from app.clients import open_meteo
from app.clients.open_meteo import pick_forecast_hour

# Hourly times as Open-Meteo returns them with timezone=auto: local, no offset.
TIMES = [f"2026-11-{day}T{hour:02d}:00" for day in (13, 14) for hour in range(24)]
WARSAW_WINTER = 3600  # UTC+1


def _at(hh: int, mm: int = 0, day: int = 13) -> datetime:
    """A UTC instant that is hh:mm local time in Warsaw (UTC+1) on 2026-11-<day>."""
    return datetime(2026, 11, day, hh - 1, mm, tzinfo=UTC)


class TestPickForecastHour:
    def test_later_today(self) -> None:
        index = pick_forecast_hour(TIMES, WARSAW_WINTER, time(8, 0), now_utc=_at(6, 30))
        assert TIMES[index] == "2026-11-13T08:00"

    def test_already_passed_today_uses_tomorrow(self) -> None:
        index = pick_forecast_hour(TIMES, WARSAW_WINTER, time(8, 0), now_utc=_at(8, 10))
        assert TIMES[index] == "2026-11-14T08:00"

    def test_uses_local_time_not_utc(self) -> None:
        # 07:30 local = 06:30 UTC. Comparing in UTC would wrongly pick today 07:00.
        index = pick_forecast_hour(TIMES, WARSAW_WINTER, time(7, 0), now_utc=_at(7, 30))
        assert TIMES[index] == "2026-11-14T07:00"

    def test_rounds_to_nearest_hour(self) -> None:
        early = pick_forecast_hour(TIMES, WARSAW_WINTER, time(8, 20), now_utc=_at(6))
        late = pick_forecast_hour(TIMES, WARSAW_WINTER, time(8, 40), now_utc=_at(6))
        assert TIMES[early] == "2026-11-13T08:00"
        assert TIMES[late] == "2026-11-13T09:00"

    def test_late_departure_rounds_into_the_next_day(self) -> None:
        index = pick_forecast_hour(TIMES, WARSAW_WINTER, time(23, 45), now_utc=_at(6))
        assert TIMES[index] == "2026-11-14T00:00"

    def test_returns_none_when_hour_not_in_forecast(self) -> None:
        index = pick_forecast_hour(TIMES[:5], WARSAW_WINTER, time(23, 0), now_utc=_at(6))
        assert index is None


def _hourly_response(**overrides: object) -> httpx.Response:
    hourly = {
        "time": TIMES,
        "temperature_2m": [4.0] * len(TIMES),
        "precipitation": [0.0] * len(TIMES),
        "wind_speed_10m": [12.0] * len(TIMES),
        "weather_code": [3] * len(TIMES),
    }
    hourly.update(overrides)
    return httpx.Response(
        200,
        json={"utc_offset_seconds": WARSAW_WINTER, "hourly": hourly},
        request=httpx.Request("GET", "https://upstream.test"),
    )


class TestGetForecastAt:
    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_weather_for_the_departure_hour(self, mock_get: MagicMock) -> None:
        precipitation = [0.0] * len(TIMES)
        precipitation[TIMES.index("2026-11-14T08:00")] = 1.4
        mock_get.return_value = _hourly_response(precipitation=precipitation)

        result = open_meteo.get_forecast_at(54.35, 18.64, time(8, 0), now_utc=_at(9))

        assert result is not None
        assert result.time == "2026-11-14T08:00"
        assert result.departure_day == "tomorrow"
        assert result.weather.precipitation_mm == 1.4
        params = mock_get.call_args.kwargs["params"]
        assert params["timezone"] == "auto"
        assert "precipitation" in params["hourly"]

    @patch("app.clients.open_meteo.httpx.get")
    def test_labels_by_departure_day_not_by_rounded_slot(self, mock_get: MagicMock) -> None:
        # 23:45 today uses the 00:00 slot (tomorrow's date), but the *departure* is today.
        mock_get.return_value = _hourly_response()

        result = open_meteo.get_forecast_at(54.35, 18.64, time(23, 45), now_utc=_at(6))

        assert result is not None
        assert result.time == "2026-11-14T00:00"
        assert result.departure_day == "today"

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_on_null_value_at_that_hour(self, mock_get: MagicMock) -> None:
        temps: list[float | None] = [4.0] * len(TIMES)
        temps[TIMES.index("2026-11-13T08:00")] = None
        mock_get.return_value = _hourly_response(temperature_2m=temps)

        assert open_meteo.get_forecast_at(54.35, 18.64, time(8, 0), now_utc=_at(6)) is None

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_on_timeout(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = httpx.TimeoutException("timed out")

        assert open_meteo.get_forecast_at(54.35, 18.64, time(8, 0)) is None

    @patch("app.clients.open_meteo.httpx.get")
    def test_returns_none_without_hourly_block(self, mock_get: MagicMock) -> None:
        mock_get.return_value = httpx.Response(
            200, json={"latitude": 1}, request=httpx.Request("GET", "https://upstream.test")
        )

        assert open_meteo.get_forecast_at(54.35, 18.64, time(8, 0)) is None
