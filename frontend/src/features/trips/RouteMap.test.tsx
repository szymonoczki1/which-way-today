import { render, screen } from "@testing-library/react";
import L from "leaflet";
import { describe, expect, it, vi } from "vitest";

import { makeTrip } from "../../test/utils";
import RouteMap from "./RouteMap";

describe("RouteMap", () => {
  it("renders a map with OpenStreetMap attribution", () => {
    const { container } = render(<RouteMap trip={makeTrip()} />);

    expect(container.querySelector(".leaflet-container")).not.toBeNull();
    expect(screen.getByText(/openstreetmap/i)).toBeInTheDocument();
  });

  it("labels the map with the trip's origin and destination", () => {
    render(<RouteMap trip={makeTrip()} />);

    expect(
      screen.getByRole("region", {
        name: /map.*gdansk main station.*gdansk university of technology/i,
      }),
    ).toBeInTheDocument();
  });

  it("refits the view when a different trip is selected", () => {
    const fitBounds = vi.spyOn(L.Map.prototype, "fitBounds");
    const { rerender } = render(<RouteMap trip={makeTrip()} />);

    const other = makeTrip({
      id: 2,
      origin_lat: 52.23,
      origin_lon: 21.01,
      destination_lat: 52.25,
      destination_lon: 21.0,
    });
    rerender(<RouteMap trip={other} />);

    const lastBounds = fitBounds.mock.lastCall?.[0];
    expect(JSON.stringify(lastBounds)).toContain("52.23");
    expect(JSON.stringify(lastBounds)).toContain("21.01");
  });
});
