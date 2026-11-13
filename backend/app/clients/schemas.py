from pydantic import BaseModel


class GeocodeResult(BaseModel):
    lat: float
    lon: float
    display_name: str


class RouteResult(BaseModel):
    distance_m: float
    duration_s: float
    # [[lat, lon], ...] -- pre-flipped from OSRM's [lon, lat] GeoJSON order so
    # the frontend can feed this straight into a Leaflet Polyline.
    geometry: list[list[float]]


class WeatherResult(BaseModel):
    temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float
    weather_code: int


class TransitLeg(BaseModel):
    # Transitous/MOTIS mode: WALK, BUS, TRAM, REGIONAL_RAIL, LONG_DISTANCE, ...
    mode: str
    line: str | None  # e.g. "6", "168", "IC"
    headsign: str | None  # direction shown on the vehicle
    agency: str | None  # operator, e.g. "Zarząd Transportu Miejskiego w Gdańsku"
    from_name: str
    to_name: str
    start_time: str  # ISO 8601 UTC, e.g. "2026-11-14T07:04:00Z"
    end_time: str
    duration_min: float
    distance_km: float
    geometry: list[list[float]]  # [[lat, lon], ...]


class TransitJourney(BaseModel):
    duration_min: float
    transfers: int
    start_time: str
    end_time: str
    legs: list[TransitLeg]
