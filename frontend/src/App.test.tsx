import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import type { ModeOption, Trip, TripComparison } from "./lib/types";
import { makeTrip, renderWithClient } from "./test/utils";

// Leaflet is covered in RouteMap.test.tsx; here we only care which trip the
// shell hands to the (lazy-loaded) map.
vi.mock("./features/trips/RouteMap", () => ({
  default: ({ trip, routes }: { trip: Trip; routes?: ModeOption[] }) => (
    <div>
      <div>Map of {trip.name}</div>
      <div>Route lines: {routes?.filter((r) => r.geometry).length ?? 0}</div>
    </div>
  ),
}));

const COMPARISON: TripComparison = {
  trip_id: 2,
  weather: null,
  options: [
    {
      mode: "walk",
      duration_min: 35,
      distance_km: 2.7,
      cost_pln: 0,
      co2_g: 0,
      is_estimate: false,
      geometry: [
        [54.3, 18.6],
        [54.4, 18.7],
      ],
    },
    {
      mode: "bike",
      duration_min: 11,
      distance_km: 2.7,
      cost_pln: 0,
      co2_g: 0,
      is_estimate: true,
      geometry: null,
    },
    {
      mode: "transit",
      duration_min: 16,
      distance_km: 2.7,
      cost_pln: 4.8,
      co2_g: 161,
      is_estimate: true,
      geometry: null,
    },
    {
      mode: "car",
      duration_min: 5,
      distance_km: 2.7,
      cost_pln: 1.21,
      co2_g: 456,
      is_estimate: false,
      geometry: [
        [54.3, 18.6],
        [54.4, 18.7],
      ],
    },
  ],
};

function stubBackend({ healthy = true, trips = [] as Trip[] } = {}) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = String(input);
    if (url.endsWith("/health")) {
      if (!healthy) throw new TypeError("Failed to fetch");
      return Response.json({ status: "ok" });
    }
    if (url.endsWith("/trips")) return Response.json(trips);
    if (/\/trips\/\d+\/comparison$/.test(url)) return Response.json(COMPARISON);
    return new Response(null, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
}

describe("App shell", () => {
  it("renders the title and main sections", () => {
    stubBackend();

    renderWithClient(<App />);

    expect(
      screen.getByRole("heading", { level: 1, name: /which way today/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /your trips/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: /comparison/i }),
    ).toBeInTheDocument();
  });

  it("shows the backend as connected when /health responds", async () => {
    stubBackend();

    renderWithClient(<App />);

    expect(screen.getByRole("status")).toHaveTextContent(/checking/i);
    expect(await screen.findByText(/backend connected/i)).toBeInTheDocument();
  });

  it("shows the backend as offline when /health fails", async () => {
    stubBackend({ healthy: false });

    renderWithClient(<App />);

    expect(await screen.findByText(/backend offline/i)).toBeInTheDocument();
  });

  it("prompts to select a trip until one is selected, then shows its map", async () => {
    stubBackend({
      trips: [makeTrip(), makeTrip({ id: 2, name: "Home -> Gym" })],
    });
    const user = userEvent.setup();

    renderWithClient(<App />);

    expect(await screen.findByText(/select a trip/i)).toBeInTheDocument();
    await user.click(
      await screen.findByRole("button", { name: "Home -> Gym" }),
    );

    expect(await screen.findByText("Map of Home -> Gym")).toBeInTheDocument();
  });

  it("selects a newly created trip, and returns to the placeholder when it is deleted", async () => {
    // Small in-memory backend so create -> list -> delete round-trips for real.
    let trips: Trip[] = [];
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        const url = new URL(String(input));
        const method = init?.method ?? "GET";
        if (url.pathname === "/health") return Response.json({ status: "ok" });
        if (url.pathname === "/geocode")
          return Response.json({ lat: 54.35, lon: 18.64, display_name: "x" });
        if (url.pathname === "/trips" && method === "GET")
          return Response.json(trips);
        if (url.pathname === "/trips" && method === "POST") {
          const trip = { id: 5, ...JSON.parse(String(init?.body)) } as Trip;
          trips = [trip];
          return Response.json(trip, { status: 201 });
        }
        if (url.pathname === "/trips/5" && method === "DELETE") {
          trips = [];
          return new Response(null, { status: 204 });
        }
        return new Response(null, { status: 404 });
      }),
    );
    const user = userEvent.setup();

    renderWithClient(<App />);
    await user.type(screen.getByLabelText(/trip name/i), "Home -> Pool");
    await user.type(screen.getByLabelText(/from/i), "Home");
    await user.type(screen.getByLabelText(/to/i), "Pool");
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    expect(await screen.findByText("Map of Home -> Pool")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Delete Home -> Pool" }),
    );

    expect(await screen.findByText(/select a trip/i)).toBeInTheDocument();
    expect(screen.queryByText("Map of Home -> Pool")).toBeNull();
  });

  it("shows the comparison for the selected trip and passes live routes to the map", async () => {
    stubBackend({ trips: [makeTrip({ id: 2, name: "Home -> Gym" })] });
    const user = userEvent.setup();

    renderWithClient(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Home -> Gym" }),
    );

    expect(
      await screen.findByRole("listitem", { name: /car/i }),
    ).toHaveTextContent("1.21 zł");
    expect(await screen.findByText("Route lines: 2")).toBeInTheDocument();
    // App (for the map) and ComparisonPanel share one query: exactly one request.
    const comparisonCalls = vi
      .mocked(fetch)
      .mock.calls.filter(([url]) =>
        /\/trips\/2\/comparison$/.test(String(url)),
      );
    expect(comparisonCalls).toHaveLength(1);
  });

  it("does not show a deleted trip's cached comparison for a new trip that reuses its id", async () => {
    // SQLite reuses the highest deleted id, so "trip 5" can be two different trips.
    let trips: Trip[] = [makeTrip({ id: 5, name: "Old trip" })];
    let comparisonVersion = 0;
    vi.spyOn(window, "confirm").mockReturnValue(true);
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>(async (input, init) => {
        const url = new URL(String(input));
        const method = init?.method ?? "GET";
        if (url.pathname === "/health") return Response.json({ status: "ok" });
        if (url.pathname === "/geocode")
          return Response.json({ lat: 54.35, lon: 18.64, display_name: "x" });
        if (url.pathname === "/trips" && method === "GET")
          return Response.json(trips);
        if (url.pathname === "/trips" && method === "POST") {
          const trip = { id: 5, ...JSON.parse(String(init?.body)) } as Trip;
          trips = [trip];
          return Response.json(trip, { status: 201 });
        }
        if (url.pathname === "/trips/5" && method === "DELETE") {
          trips = [];
          return new Response(null, { status: 204 });
        }
        if (url.pathname === "/trips/5/comparison") {
          comparisonVersion += 1;
          const carCost = comparisonVersion === 1 ? 1.21 : 9.99;
          return Response.json({
            ...COMPARISON,
            trip_id: 5,
            options: COMPARISON.options.map((o) =>
              o.mode === "car" ? { ...o, cost_pln: carCost } : o,
            ),
          });
        }
        return new Response(null, { status: 404 });
      }),
    );
    const user = userEvent.setup();

    renderWithClient(<App />);
    await user.click(await screen.findByRole("button", { name: "Old trip" }));
    expect(await screen.findByText("1.21 zł")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete Old trip" }));
    await screen.findByText(/no trips yet/i);

    await user.type(screen.getByLabelText(/trip name/i), "New trip");
    await user.type(screen.getByLabelText(/from/i), "Home");
    await user.type(screen.getByLabelText(/to/i), "Pool");
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    expect(await screen.findByText("9.99 zł")).toBeInTheDocument();
    expect(screen.queryByText("1.21 zł")).toBeNull();
  });

  describe("on narrow screens", () => {
    function setScreen(narrow: boolean) {
      vi.stubGlobal(
        "matchMedia",
        vi.fn(
          (query: string) =>
            ({ matches: narrow, media: query }) as MediaQueryList,
        ),
      );
      // jsdom doesn't implement scrollIntoView.
      const scroll = vi.fn();
      Element.prototype.scrollIntoView = scroll;
      return scroll;
    }

    afterEach(() => {
      // @ts-expect-error -- remove the stub so other tests see jsdom's default
      delete Element.prototype.scrollIntoView;
    });

    it("scrolls the selected trip's details into view (they're below the form)", async () => {
      const scroll = setScreen(true);
      stubBackend({ trips: [makeTrip({ id: 2, name: "Home -> Gym" })] });
      const user = userEvent.setup();

      renderWithClient(<App />);
      await user.click(
        await screen.findByRole("button", { name: "Home -> Gym" }),
      );

      await vi.waitFor(() => expect(scroll).toHaveBeenCalled());
      const target = scroll.mock.contexts[0] as HTMLElement;
      expect(target).toHaveAccessibleName("Home -> Gym");
    });

    it("scrolls again when the already-selected trip is tapped again", async () => {
      const scroll = setScreen(true);
      stubBackend({ trips: [makeTrip({ id: 2, name: "Home -> Gym" })] });
      const user = userEvent.setup();

      renderWithClient(<App />);
      const trip = await screen.findByRole("button", { name: "Home -> Gym" });
      await user.click(trip);
      await vi.waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
      // User scrolled back up to the list and taps the same trip.
      await user.click(trip);

      await vi.waitFor(() => expect(scroll).toHaveBeenCalledTimes(2));
    });

    it("does not scroll on first load or on background refetches", async () => {
      const scroll = setScreen(true);
      stubBackend({ trips: [makeTrip({ id: 2, name: "Home -> Gym" })] });

      const { client } = renderWithClient(<App />);
      await screen.findByRole("button", { name: "Home -> Gym" });
      await client.refetchQueries({ queryKey: ["trips"] });

      expect(scroll).not.toHaveBeenCalled();
    });

    it("does not scroll on wide screens, where details are beside the list", async () => {
      const scroll = setScreen(false);
      stubBackend({ trips: [makeTrip({ id: 2, name: "Home -> Gym" })] });
      const user = userEvent.setup();

      renderWithClient(<App />);
      await user.click(
        await screen.findByRole("button", { name: "Home -> Gym" }),
      );
      await screen.findByText("Map of Home -> Gym");

      expect(scroll).not.toHaveBeenCalled();
    });
  });
});
