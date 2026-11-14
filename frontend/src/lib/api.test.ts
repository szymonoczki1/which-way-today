import { describe, expect, it, vi } from "vitest";

import {
  API_URL,
  ApiError,
  createTrip,
  deleteTrip,
  geocode,
  getComparison,
  getHealth,
  getRouteComparison,
  getRouteRecommendation,
  listTrips,
  resolveApiUrl,
} from "./api";
import type { TripInput } from "./types";

const TRIP_INPUT: TripInput = {
  name: "Home -> Uni",
  origin_address: "Gdansk Main Station",
  origin_lat: 54.355,
  origin_lon: 18.646,
  destination_address: "Gdansk University of Technology",
  destination_lat: 54.371,
  destination_lon: 18.613,
  usual_departure_time: null,
};

function mockFetch(response: Response | Error) {
  const fn = vi.fn<typeof fetch>();
  if (response instanceof Error) fn.mockRejectedValue(response);
  else fn.mockResolvedValue(response);
  vi.stubGlobal("fetch", fn);
  return fn;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("resolveApiUrl", () => {
  it.each([undefined, "", "   "])(
    "falls back to the local backend for %j (zero-config)",
    (raw) => {
      expect(resolveApiUrl(raw)).toBe("http://localhost:8000");
    },
  );

  it("strips trailing slashes so paths join cleanly", () => {
    expect(resolveApiUrl("http://api.example:8000//")).toBe(
      "http://api.example:8000",
    );
  });
});

describe("request helpers", () => {
  it("GETs trips from the configured base URL", async () => {
    const fetchMock = mockFetch(json([]));

    await expect(listTrips()).resolves.toEqual([]);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_URL}/trips`,
      expect.anything(),
    );
  });

  it("POSTs a trip as JSON", async () => {
    const fetchMock = mockFetch(json({ id: 1, ...TRIP_INPUT }, 201));

    const trip = await createTrip(TRIP_INPUT);

    expect(trip.id).toBe(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`${API_URL}/trips`);
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe(
      "application/json",
    );
    expect(JSON.parse(init?.body as string)).toEqual(TRIP_INPUT);
  });

  it("resolves to undefined on 204 No Content", async () => {
    mockFetch(new Response(null, { status: 204 }));

    await expect(deleteTrip(1)).resolves.toBeUndefined();
  });

  it("URL-encodes the geocode query", async () => {
    const fetchMock = mockFetch(
      json({ lat: 54.35, lon: 18.64, display_name: "Gdańsk" }),
    );

    await geocode("Długa 1, Gdańsk & co");

    const url = new URL(fetchMock.mock.calls[0][0] as string);
    expect(url.pathname).toBe("/geocode");
    expect(url.searchParams.get("q")).toBe("Długa 1, Gdańsk & co");
  });

  it("returns a comparison with nullable weather and geometry", async () => {
    mockFetch(
      json({
        trip_id: 1,
        weather: null,
        options: [
          {
            mode: "transit",
            duration_min: 16,
            distance_km: 2.68,
            cost_pln: 4.8,
            co2_g: 161,
            is_estimate: true,
            geometry: null,
          },
        ],
      }),
    );

    const comparison = await getComparison(1);

    expect(comparison.weather).toBeNull();
    expect(comparison.options[0].geometry).toBeNull();
  });
});

describe("errors", () => {
  it("throws ApiError with the backend detail on 404", async () => {
    mockFetch(json({ detail: "Address not found: nowhere" }, 404));

    const error = await geocode("nowhere").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).message).toBe("Address not found: nowhere");
  });

  it("keeps 503 distinguishable from 404 for geocoding", async () => {
    mockFetch(
      json({ detail: "Geocoding service is temporarily unavailable" }, 503),
    );

    const error = (await geocode("Gdansk").catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error.status).toBe(503);
  });

  it("handles FastAPI 422 validation detail (a list, not a string)", async () => {
    mockFetch(
      json(
        {
          detail: [
            {
              loc: ["body", "origin_lat"],
              msg: "Input should be less than or equal to 90",
            },
          ],
        },
        422,
      ),
    );

    const error = (await createTrip(TRIP_INPUT).catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error.status).toBe(422);
    expect(error.message).toBe(
      "origin_lat: Input should be less than or equal to 90",
    );
  });

  it("names each field in a multi-error 422", async () => {
    mockFetch(
      json(
        {
          detail: [
            { loc: ["body", "name"], msg: "Field required" },
            { loc: ["body", "origin_address"], msg: "Field required" },
          ],
        },
        422,
      ),
    );

    const error = (await createTrip(TRIP_INPUT).catch(
      (e: unknown) => e,
    )) as ApiError;

    expect(error.message).toBe(
      "name: Field required; origin_address: Field required",
    );
  });

  it("wraps a non-JSON 2xx body (e.g. index.html) as ApiError", async () => {
    mockFetch(new Response("<!doctype html><html></html>", { status: 200 }));

    const error = (await listTrips().catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(200);
    expect(error.message).toMatch(/unexpected response/i);
  });

  it("falls back to a generic message for a non-JSON error body", async () => {
    mockFetch(new Response("<html>Bad Gateway</html>", { status: 502 }));

    const error = (await listTrips().catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.message).toMatch(/502/);
  });

  it("wraps network failures as ApiError with status 0", async () => {
    mockFetch(new TypeError("Failed to fetch"));

    const error = (await getHealth().catch((e: unknown) => e)) as ApiError;

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.message).toMatch(/reach the server/i);
  });
});

describe("unsaved routes", () => {
  const ROUTE = {
    origin_lat: 54.3557,
    origin_lon: 18.644,
    destination_lat: 54.3713,
    destination_lon: 18.6123,
    departure_time: "08:00",
  };

  it("sends the route as query parameters", async () => {
    const fetchMock = mockFetch(
      json({ trip_id: null, weather: null, options: [] }),
    );

    await getRouteComparison(ROUTE);

    const url = new URL(fetchMock.mock.calls[0][0] as string);
    expect(url.pathname).toBe("/routes/comparison");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      origin_lat: "54.3557",
      origin_lon: "18.644",
      destination_lat: "54.3713",
      destination_lon: "18.6123",
      departure_time: "08:00",
    });
  });

  it("omits departure_time when there isn't one", async () => {
    const fetchMock = mockFetch(json({}));

    await getRouteRecommendation({ ...ROUTE, departure_time: null });

    const url = new URL(fetchMock.mock.calls[0][0] as string);
    expect(url.pathname).toBe("/routes/recommendation");
    expect(url.searchParams.has("departure_time")).toBe(false);
  });
});
