// Mirrors backend/app/schemas.py and backend/app/clients/schemas.py.
// Keep in sync by hand when the backend contract changes.

export interface TripInput {
  name: string;
  origin_address: string;
  origin_lat: number;
  origin_lon: number;
  destination_address: string;
  destination_lat: number;
  destination_lon: number;
  /**
   * Sent as "HH:MM" or "HH:MM:SS"; returned as "HH:MM:SS" (or with .ffffff if
   * seconds had a fraction). Use null, never "", for "no usual time": an empty
   * <input type="time"> gives "" and the backend rejects it with a 422.
   */
  usual_departure_time: string | null;
}

export interface Trip extends TripInput {
  id: number;
}

export interface GeocodeResult {
  lat: number;
  lon: number;
  display_name: string;
}

export interface Weather {
  temperature_c: number;
  precipitation_mm: number;
  wind_speed_kmh: number;
  /** WMO weather interpretation code. */
  weather_code: number;
}

export type Mode = "walk" | "bike" | "transit" | "car";

export interface ModeOption {
  mode: Mode;
  duration_min: number;
  distance_km: number;
  cost_pln: number;
  co2_g: number;
  /** True when numbers come from static factors (always for transit). */
  is_estimate: boolean;
  /** [[lat, lon], ...] for a Leaflet Polyline; null for estimates and transit. */
  geometry: [number, number][] | null;
}

export interface TripComparison {
  trip_id: number;
  /** null when the weather service failed or timed out. */
  weather: Weather | null;
  options: ModeOption[];
}

export interface RecommendationWeather extends Weather {
  /** Local forecast hour, e.g. "2026-11-14T08:00"; null for current conditions. */
  time: string | null;
  is_forecast: boolean;
}

export interface Recommendation {
  trip_id: number;
  /** "ai" when the LLM answered validly; "rules" for the deterministic fallback. */
  source: "ai" | "rules";
  recommended_mode: Mode;
  headline: string;
  reasons: string[];
  weather: RecommendationWeather | null;
}
