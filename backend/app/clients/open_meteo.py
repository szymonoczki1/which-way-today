import logging

import httpx
from pydantic import ValidationError

from app.clients.schemas import WeatherResult

logger = logging.getLogger(__name__)

BASE_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = httpx.Timeout(5.0, connect=3.0)


def get_current_weather(lat: float, lon: float) -> WeatherResult | None:
    try:
        response = httpx.get(
            BASE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
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
