import type { GeocodeResult, Trip, TripComparison, TripInput } from "./types";

const DEFAULT_API_URL = "http://localhost:8000";

/** Pure so the zero-config fallback is testable regardless of the local .env. */
export function resolveApiUrl(raw: string | undefined): string {
  const trimmed = raw?.trim();
  return (trimmed || DEFAULT_API_URL).replace(/\/+$/, "");
}

// The only place VITE_API_URL is read. It is baked in at build time, so in
// Docker it must be a URL the *browser* can reach (not a compose service name).
export const API_URL = resolveApiUrl(import.meta.env.VITE_API_URL);

/**
 * Any failed API call. `status` is the HTTP status, or 0 if the server could not
 * be reached at all. `message` is the backend's `detail` when it sent one, so it
 * can be shown to the user as-is.
 */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    // Also what the browser reports for a CORS rejection, so don't claim the
    // backend is down for certain.
    throw new ApiError(
      0,
      "Could not reach the server (backend down, network or CORS issue).",
    );
  }

  if (!response.ok) {
    throw new ApiError(response.status, await errorMessage(response));
  }
  if (response.status === 204) return undefined as T;
  try {
    return (await response.json()) as T;
  } catch {
    // e.g. VITE_API_URL pointing at a server that answers with index.html.
    throw new ApiError(response.status, "Unexpected response from server");
  }
}

async function errorMessage(response: Response): Promise<string> {
  const fallback = `Request failed (${response.status})`;
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown })?.detail;
    if (typeof detail === "string") return detail;
    // FastAPI 422s carry a list of {loc, msg, ...} validation errors; prefix
    // each with its field name (last loc element) so it reads on its own.
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          const { loc, msg } = (item ?? {}) as { loc?: unknown; msg?: unknown };
          if (typeof msg !== "string") return null;
          const field = Array.isArray(loc) ? loc.at(-1) : undefined;
          return field !== undefined ? `${field}: ${msg}` : msg;
        })
        .filter((msg): msg is string => msg !== null);
      if (messages.length > 0) return messages.join("; ");
    }
    return fallback;
  } catch {
    // Non-JSON body, e.g. an HTML error page from a proxy.
    return fallback;
  }
}

export const getHealth = () => request<{ status: string }>("/health");

export const listTrips = () => request<Trip[]>("/trips");
export const getTrip = (id: number) => request<Trip>(`/trips/${id}`);
export const createTrip = (data: TripInput) =>
  request<Trip>("/trips", { method: "POST", body: JSON.stringify(data) });
export const updateTrip = (id: number, data: TripInput) =>
  request<Trip>(`/trips/${id}`, { method: "PUT", body: JSON.stringify(data) });
export const deleteTrip = (id: number) =>
  request<void>(`/trips/${id}`, { method: "DELETE" });

/** 404 = address not found, 503 = geocoding temporarily unavailable. */
export const geocode = (query: string) =>
  request<GeocodeResult>(`/geocode?${new URLSearchParams({ q: query })}`);

export const getComparison = (tripId: number) =>
  request<TripComparison>(`/trips/${tripId}/comparison`);
