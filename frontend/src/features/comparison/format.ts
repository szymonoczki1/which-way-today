// Pure display helpers for the comparison view.

export function formatDuration(minutes: number): string {
  if (minutes <= 0) return "0 min";
  // Never show "0 min" for a real, non-zero trip.
  const total = Math.max(1, Math.round(minutes));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours === 0) return `${mins} min`;
  return mins === 0 ? `${hours} h` : `${hours} h ${mins} min`;
}

export function formatDistance(km: number): string {
  // Don't show "0 km" next to a non-zero duration for very short hops.
  if (km > 0 && km < 0.05) return "<0.1 km";
  // One decimal for short trips, whole km once the decimal stops mattering.
  const value = km < 10 ? Math.round(km * 10) / 10 : Math.round(km);
  return `${value} km`;
}

export function formatCost(pln: number | null): string {
  if (pln === null) return "Varies"; // depends on operator / ticket type
  return pln === 0 ? "Free" : `${pln.toFixed(2)} zł`;
}

const ZONE = "Europe/Warsaw"; // trips are in Gdańsk, whatever the viewer's zone
const CLOCK = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: ZONE,
});
const DAY = new Intl.DateTimeFormat("en-CA", { timeZone: ZONE }); // YYYY-MM-DD
const WEEKDAY = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  timeZone: ZONE,
});

/** Departure with its day when it isn't today: "08:04", "04:30 tomorrow", "08:00 on Mon". */
export function formatDeparture(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const days = Math.round(
    (Date.parse(DAY.format(date)) - Date.parse(DAY.format(now))) / 86_400_000,
  );
  const clock = CLOCK.format(date);
  if (days === 0) return clock;
  if (days === 1) return `${clock} tomorrow`;
  return `${clock} on ${WEEKDAY.format(date)}`;
}

export function formatCo2(grams: number): string {
  return grams < 1000
    ? `${Math.round(grams)} g`
    : `${(grams / 1000).toFixed(1)} kg`;
}

interface WeatherDescription {
  label: string;
  icon: string;
}

// WMO weather interpretation codes, as returned by Open-Meteo.
// https://open-meteo.com/en/docs (section "WMO Weather interpretation codes")
const WMO: Record<number, WeatherDescription> = {
  0: { label: "Clear sky", icon: "☀️" },
  1: { label: "Mainly clear", icon: "🌤️" },
  2: { label: "Partly cloudy", icon: "⛅" },
  3: { label: "Overcast", icon: "☁️" },
  45: { label: "Fog", icon: "🌫️" },
  48: { label: "Freezing fog", icon: "🌫️" },
  51: { label: "Light drizzle", icon: "🌦️" },
  53: { label: "Drizzle", icon: "🌦️" },
  55: { label: "Heavy drizzle", icon: "🌧️" },
  56: { label: "Freezing drizzle", icon: "🌧️" },
  57: { label: "Heavy freezing drizzle", icon: "🌧️" },
  61: { label: "Light rain", icon: "🌦️" },
  63: { label: "Rain", icon: "🌧️" },
  65: { label: "Heavy rain", icon: "🌧️" },
  66: { label: "Freezing rain", icon: "🌧️" },
  67: { label: "Heavy freezing rain", icon: "🌧️" },
  71: { label: "Light snow", icon: "🌨️" },
  73: { label: "Snow", icon: "🌨️" },
  75: { label: "Heavy snow", icon: "❄️" },
  77: { label: "Snow grains", icon: "🌨️" },
  80: { label: "Light rain showers", icon: "🌦️" },
  81: { label: "Rain showers", icon: "🌧️" },
  82: { label: "Violent rain showers", icon: "⛈️" },
  85: { label: "Snow showers", icon: "🌨️" },
  86: { label: "Heavy snow showers", icon: "❄️" },
  95: { label: "Thunderstorm", icon: "⛈️" },
  96: { label: "Thunderstorm with hail", icon: "⛈️" },
  99: { label: "Thunderstorm with heavy hail", icon: "⛈️" },
};

export function describeWeather(code: number): WeatherDescription {
  return WMO[code] ?? { label: "Unknown conditions", icon: "🌡️" };
}
