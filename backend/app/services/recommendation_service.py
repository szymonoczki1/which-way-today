"""Weather-aware "which way today?" recommendation for a saved trip.

1. Get the trip's comparison (shared with /comparison, so the numbers match the
   cards) and, if the trip has a usual departure time, the hourly forecast for it,
   in parallel under one deadline. Fall back to current weather.
2. Rule-based recommendation (deterministic, always available). It also lists
   which modes are unsuitable and why (too long, too wet, too windy...).
3. If an OpenAI key is set, let the model choose among the *suitable* modes and
   explain why, from the same facts. Any failure or invalid answer -> the rules.
   The headline is always built here from the chosen mode, so it can't contradict it.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.clients import open_meteo, openai_client
from app.clients.open_meteo import ForecastResult
from app.clients.schemas import WeatherResult
from app.config import get_settings
from app.models import Trip
from app.schemas import Mode, ModeOption, Recommendation, RecommendationWeather
from app.services import comparison_service
from app.services.comparison_service import get_shared_comparison

logger = logging.getLogger(__name__)

# The forecast must arrive within the comparison's own budget (+ a little slack);
# otherwise we use current weather. The optional AI call adds at most ~8 s on top.
DEADLINE_S = comparison_service.DEADLINE_S + 0.5

# --- Rule thresholds (MVP assumptions, documented so they can be defended) ---
MAX_WALK_MIN = 25  # longer walks are a stretch for a daily commute
MAX_WET_WALK_MIN = 10  # in rain/snow, only very short walks
MAX_BIKE_MIN = 35
WET_PRECIP_MM = 0.5  # mm in the hour: noticeably wet
MAX_BIKE_WIND_KMH = 30  # gusty enough to make cycling unpleasant/unsafe
MIN_BIKE_TEMP_C = 0  # below freezing: ice risk
# Prefer transit over the car unless it takes more than 2x the car time + 10 min.
TRANSIT_SLOWDOWN_FACTOR = 2
TRANSIT_SLOWDOWN_EXTRA_MIN = 10

# WMO weather codes (Open-Meteo): drizzle/rain/showers/thunderstorm, and snow.
WET_CODES = set(range(51, 68)) | {80, 81, 82, 95, 96, 99}
SNOW_CODES = set(range(71, 78)) | {85, 86}

GREEN_FIRST: tuple[Mode, ...] = ("walk", "bike", "transit", "car")
ACTION: dict[Mode, str] = {
    "walk": "Walk",
    "bike": "Take the bike",
    "transit": "Take public transport",
    "car": "Drive",
}


class RuleResult(BaseModel):
    recommended_mode: Mode
    reasons: list[str]
    # Modes the rules consider unreasonable right now, with the reason.
    unsuitable: dict[Mode, str]


def rule_based_recommendation(
    options: list[ModeOption], weather: WeatherResult | None, when: str
) -> RuleResult:
    """Greenest option that suits the weather and isn't unreasonably slow.

    `when` describes the weather's time for the explanation: "now" or "at 08:00".
    """
    by_mode = {o.mode: o for o in options}
    walk, bike, transit, car = (by_mode[m] for m in GREEN_FIRST)

    wet = weather is not None and (
        weather.precipitation_mm >= WET_PRECIP_MM or weather.weather_code in WET_CODES
    )
    snowy = weather is not None and weather.weather_code in SNOW_CODES

    unsuitable: dict[Mode, str] = {}
    walk_limit = MAX_WET_WALK_MIN if (wet or snowy) else MAX_WALK_MIN
    if walk.duration_min > walk_limit:
        unsuitable["walk"] = (
            "Too wet for a longer walk."
            if walk.duration_min <= MAX_WALK_MIN
            else f"Walking would take {_minutes(walk)}."
        )
    bike_blocker = _bike_blocker(weather, wet, snowy)
    if bike_blocker:
        unsuitable["bike"] = bike_blocker
    elif bike.duration_min > MAX_BIKE_MIN:
        unsuitable["bike"] = f"Cycling would take {_minutes(bike)}."
    if (
        transit.duration_min
        > car.duration_min * TRANSIT_SLOWDOWN_FACTOR + TRANSIT_SLOWDOWN_EXTRA_MIN
    ):
        unsuitable["transit"] = (
            f"Public transport would take about {_minutes(transit)}, "
            f"far longer than {_minutes(car)} by car."
        )

    mode = next(m for m in GREEN_FIRST if m not in unsuitable)  # car is never unsuitable
    chosen = by_mode[mode]

    reasons = [_describe_weather(weather, when)]
    reasons += [unsuitable[m] for m in GREEN_FIRST[: GREEN_FIRST.index(mode)]]
    reasons.append(
        {
            "walk": f"It's only a {_minutes(walk)} walk.",
            "bike": f"Cycling takes {_minutes(bike)} vs {_minutes(car)} by car.",
            "transit": (
                f"Public transport takes about {_minutes(transit)} vs {_minutes(car)} by car."
            ),
            "car": f"Driving takes {_minutes(car)}.",
        }[mode]
    )
    if mode != "car" and car.co2_g > chosen.co2_g:
        reasons.append(f"Saves {car.co2_g - chosen.co2_g} g CO₂ compared with driving.")

    return RuleResult(recommended_mode=mode, reasons=reasons, unsuitable=unsuitable)


def _headline(option: ModeOption) -> str:
    approx = "~" if option.is_estimate else ""
    return f"{ACTION[option.mode]}: {approx}{_minutes(option)}"


def _bike_blocker(weather: WeatherResult | None, wet: bool, snowy: bool) -> str | None:
    if weather is None:
        return None
    if snowy:
        return "Snow makes cycling unsafe."
    if wet:
        return "Too wet for cycling."
    if weather.wind_speed_kmh >= MAX_BIKE_WIND_KMH:
        return f"Too windy for cycling ({round(weather.wind_speed_kmh)} km/h)."
    if weather.temperature_c < MIN_BIKE_TEMP_C:
        return "Below freezing: risk of ice for cycling."
    return None


def _describe_weather(weather: WeatherResult | None, when: str) -> str:
    if weather is None:
        return "Weather data is unavailable, so check the sky before you go."
    prefix = "Right now" if when == "now" else f"Forecast {when}"
    return (
        f"{prefix}: {_condition(weather.weather_code)}, {round(weather.temperature_c)}°C, "
        f"wind {round(weather.wind_speed_kmh)} km/h, "
        f"{weather.precipitation_mm:g} mm precipitation."
    )


def _condition(code: int) -> str:
    if code in SNOW_CODES:
        return "snow"
    if code >= 95:
        return "thunderstorm"
    if code >= 61:
        return "rain"
    if code >= 51:
        return "drizzle"
    if code in (45, 48):
        return "fog"
    return "clear" if code <= 1 else "cloudy"


def _minutes(option: ModeOption) -> str:
    return f"{max(1, round(option.duration_min))} min"


# --- AI layer -----------------------------------------------------------------

SYSTEM_PROMPT = """You help a commuter choose how to travel for one trip.
You get a JSON object with: the travel options (mode, duration_min, distance_km,
cost_pln, co2_g, is_estimate), the weather and when it applies (or null),
unsuitable_modes (modes ruled out, with the reason), and a rule_based_suggestion.
Use ONLY these facts; never invent numbers, places or times.
Never choose a mode listed in unsuitable_modes. Prefer greener modes when the
weather and time make them reasonable.
Reply with a JSON object exactly like:
{"recommended_mode": "walk" | "bike" | "transit" | "car",
 "reasons": ["<2 to 4 short sentences explaining the choice>"]}"""


class _AiAnswer(BaseModel):
    recommended_mode: Mode
    reasons: list[str] = Field(min_length=1, max_length=4)

    @field_validator("reasons")
    @classmethod
    def _non_blank_and_short(cls, reasons: list[str]) -> list[str]:
        cleaned = [r.strip() for r in reasons]
        if any(not r or len(r) > 300 for r in cleaned):
            raise ValueError("each reason must be 1-300 characters")
        return cleaned


def _ai_settings() -> tuple[str | None, str]:
    settings = get_settings()
    return settings.openai_api_key, settings.openai_model


def _ai_recommendation(
    options: list[ModeOption], weather: WeatherResult | None, when: str, rules: RuleResult
) -> _AiAnswer | None:
    api_key, model = _ai_settings()
    if not api_key or not api_key.strip():
        return None

    # Only numbers and weather: never the trip's name or addresses.
    facts = {
        "options": [o.model_dump(exclude={"geometry"}) for o in options],
        "weather": weather.model_dump() if weather else None,
        "weather_time": when,
        "unsuitable_modes": rules.unsuitable,
        "rule_based_suggestion": {
            "recommended_mode": rules.recommended_mode,
            "reasons": rules.reasons,
        },
    }
    raw = openai_client.complete_json(
        SYSTEM_PROMPT, json.dumps(facts, ensure_ascii=False), api_key=api_key, model=model
    )
    if raw is None:
        return None
    try:
        answer = _AiAnswer.model_validate(raw)
    except ValidationError:
        logger.warning("AI recommendation failed validation; using rules")
        return None
    if answer.recommended_mode in rules.unsuitable:
        logger.warning("AI picked a mode the rules ruled out; using rules")
        return None
    return answer


# --- Orchestration ------------------------------------------------------------


def recommend_trip(trip: Trip, deadline_s: float = DEADLINE_S) -> Recommendation:
    assert trip.id is not None, "only saved trips can be recommended"
    started = time.monotonic()

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        comparison_future = pool.submit(get_shared_comparison, trip)
        departure = trip.usual_departure_time
        forecast_future = (
            pool.submit(open_meteo.get_forecast_at, trip.origin_lat, trip.origin_lon, departure)
            if departure is not None
            else None
        )
        # Bounded by compare_trip's own deadline.
        comparison = comparison_future.result()
        forecast: ForecastResult | None = None
        if forecast_future is not None:
            remaining = max(0.0, deadline_s - (time.monotonic() - started))
            try:
                forecast = forecast_future.result(timeout=remaining)
            except FutureTimeout:
                logger.warning("Forecast missed the deadline; using current weather")
            except Exception:
                logger.exception("Forecast raised unexpectedly; using current weather")
    finally:
        # Don't wait for a straggling forecast (a plain `with` block would).
        pool.shutdown(wait=False, cancel_futures=True)

    if forecast is not None and departure is not None:
        weather: WeatherResult | None = forecast.weather
        when = f"{forecast.departure_day} at {departure:%H:%M}"
        weather_out = RecommendationWeather(
            **forecast.weather.model_dump(), time=forecast.time, is_forecast=True
        )
    else:
        weather = comparison.weather
        when = "now"
        weather_out = (
            RecommendationWeather(**weather.model_dump(), time=None, is_forecast=False)
            if weather is not None
            else None
        )

    rules = rule_based_recommendation(comparison.options, weather, when)
    try:
        ai = _ai_recommendation(comparison.options, weather, when, rules)
    except Exception:
        logger.exception("AI recommendation raised unexpectedly; using rules")
        ai = None

    mode = ai.recommended_mode if ai is not None else rules.recommended_mode
    by_mode = {o.mode: o for o in comparison.options}
    return Recommendation(
        trip_id=trip.id,
        source="ai" if ai is not None else "rules",
        recommended_mode=mode,
        headline=_headline(by_mode[mode]),
        reasons=ai.reasons if ai is not None else rules.reasons,
        weather=weather_out,
    )
