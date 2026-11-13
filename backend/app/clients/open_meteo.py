import logging
from datetime import UTC, datetime, time, timedelta
from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from app.clients.schemas import WeatherResult

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = httpx.Timeout(5.0, connect=3.0)
VARIABLES = "temperature_2m,precipitation,wind_speed_10m,weather_code"


class ForecastResult(BaseModel):
    weather: WeatherResult
    # Local time of the forecast hour, as Open-Meteo returns it: "2026-11-14T08:00".
    time: str
    # Day of the *departure* (not of the rounded slot: 23:45 today uses 00:00 tomorrow).
    departure_day: Literal["today", "tomorrow"]


def get_current_weather(lat: float, lon: float) -> WeatherResult | None:
    try:
        response = httpx.get(
            BASE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": VARIABLES,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        current = response.json().get("current")
        if not current:
            return None
        return WeatherResult(
            temperature_c=current["temperature_2m"],
            precipitation_mm=current["precipitation"],
            wind_speed_kmh=current["wind_speed_10m"],
            weather_code=current["weather_code"],
        )
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        ValidationError,
    ):
        # ValueError covers json.JSONDecodeError; ValidationError covers the null
        # values Open-Meteo returns for missing data points.
        logger.warning("Open-Meteo weather fetch failed for %s,%s", lat, lon, exc_info=True)
        return None


def pick_forecast_hour(
    times: list[str], utc_offset_seconds: int, departure: time, now_utc: datetime | None = None
) -> int | None:
    """Index of the hourly slot for the *next* occurrence of `departure`.

    Works in the location's local time (Open-Meteo's `timezone=auto` returns local,
    offset-free timestamps plus `utc_offset_seconds`). If today's departure has
    already passed, use tomorrow's. Rounds to the nearest hour.
    """
    target = _next_departure(utc_offset_seconds, departure, now_utc)
    if target.minute >= 30:
        target += timedelta(hours=1)
    key = target.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M")
    try:
        return times.index(key)
    except ValueError:
        return None


def _local_now(utc_offset_seconds: int, now_utc: datetime | None) -> datetime:
    # Known limitation: Open-Meteo applies one utc_offset_seconds (the offset at
    # request time) to the whole series, so on a DST-change weekend the slot can be
    # an hour off. Acceptable for a commute hint.
    now_utc = now_utc or datetime.now(UTC)
    return (now_utc + timedelta(seconds=utc_offset_seconds)).replace(tzinfo=None)


def _next_departure(utc_offset_seconds: int, departure: time, now_utc: datetime | None) -> datetime:
    local_now = _local_now(utc_offset_seconds, now_utc)
    target = datetime.combine(local_now.date(), departure)
    if target < local_now:
        target += timedelta(days=1)
    return target


def get_forecast_at(
    lat: float, lon: float, departure: time, now_utc: datetime | None = None
) -> ForecastResult | None:
    """Hourly forecast for the next occurrence of `departure`, or None on any failure."""
    try:
        response = httpx.get(
            BASE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": VARIABLES,
                "timezone": "auto",
                "forecast_days": 3,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        hourly = data["hourly"]
        offset = data["utc_offset_seconds"]
        index = pick_forecast_hour(hourly["time"], offset, departure, now_utc)
        if index is None:
            return None
        departure_at = _next_departure(offset, departure, now_utc)
        today = _local_now(offset, now_utc).date()
        return ForecastResult(
            time=hourly["time"][index],
            departure_day="today" if departure_at.date() == today else "tomorrow",
            weather=WeatherResult(
                temperature_c=hourly["temperature_2m"][index],
                precipitation_mm=hourly["precipitation"][index],
                wind_speed_kmh=hourly["wind_speed_10m"][index],
                weather_code=hourly["weather_code"][index],
            ),
        )
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        ValidationError,
    ):
        logger.warning("Open-Meteo forecast fetch failed for %s,%s", lat, lon, exc_info=True)
        return None
