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
