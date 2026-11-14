from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.clients.schemas import TransitLeg, WeatherResult


class TripBase(BaseModel):
    # Trip (SQLModel) instances are returned directly as response_model=TripRead;
    # from_attributes lets pydantic read them by attribute instead of requiring a dict.
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=100)
    origin_address: str = Field(min_length=1)
    origin_lat: float = Field(ge=-90, le=90)
    origin_lon: float = Field(ge=-180, le=180)
    destination_address: str = Field(min_length=1)
    destination_lat: float = Field(ge=-90, le=90)
    destination_lon: float = Field(ge=-180, le=180)
    usual_departure_time: time | None = None


class TripCreate(TripBase):
    pass


class TripUpdate(TripBase):
    pass


class TripRead(TripBase):
    id: int


class ModeOption(BaseModel):
    mode: Literal["walk", "bike", "transit", "car"]
    duration_min: float
    distance_km: float
    # None when unknown: public transport outside a single ZTM Gdańsk ride.
    cost_pln: float | None
    co2_g: int
    # True when the numbers come from static factors instead of a live route
    # (always true for transit; true for other modes if OSRM failed or timed out).
    is_estimate: bool
    # [[lat, lon], ...] for a Leaflet Polyline: live routes, and real transit journeys
    # (all legs joined); None for estimates.
    geometry: list[list[float]] | None = None
    # Public transport only, when a real journey was found (Transitous).
    legs: list[TransitLeg] | None = None


Mode = Literal["walk", "bike", "transit", "car"]


class RecommendationWeather(WeatherResult):
    # Local forecast hour ("2026-11-14T08:00"), or None for current conditions.
    time: str | None
    is_forecast: bool


class Recommendation(BaseModel):
    # None for a route checked without saving it (GET /routes/recommendation).
    trip_id: int | None
    # "ai" when the LLM answered validly, "rules" for the deterministic fallback.
    source: Literal["ai", "rules"]
    recommended_mode: Mode
    headline: str
    reasons: list[str]
    weather: RecommendationWeather | None


class TripComparison(BaseModel):
    # None for a route checked without saving it (GET /routes/comparison).
    trip_id: int | None
    # None if Open-Meteo failed or timed out; the comparison is still returned.
    weather: WeatherResult | None
    options: list[ModeOption]
