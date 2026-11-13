import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "./App";
import type { Trip } from "./lib/types";
import { makeTrip, renderWithClient } from "./test/utils";

// Leaflet is covered in RouteMap.test.tsx; here we only care which trip the
// shell hands to the (lazy-loaded) map.
vi.mock("./features/trips/RouteMap", () => ({
  default: ({ trip }: { trip: Trip }) => <div>Map of {trip.name}</div>,
}));

function stubBackend({ healthy = true, trips = [] as Trip[] } = {}) {
  const fetchMock = vi.fn<typeof fetch>(async (input) => {
    const url = String(input);
    if (url.endsWith("/health")) {
      if (!healthy) throw new TypeError("Failed to fetch");
      return Response.json({ status: "ok" });
    }
    if (url.endsWith("/trips")) return Response.json(trips);
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
        if (url.pathname === "/trips" && method === "GET") return Response.json(trips);
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

    await user.click(screen.getByRole("button", { name: "Delete Home -> Pool" }));

    expect(await screen.findByText(/select a trip/i)).toBeInTheDocument();
    expect(screen.queryByText("Map of Home -> Pool")).toBeNull();
  });
});
