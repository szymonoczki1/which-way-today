import { render, screen } from "@testing-library/react";
import L from "leaflet";
import { describe, expect, it, vi } from "vitest";

import type { ModeOption } from "../../lib/types";
import { makeTrip } from "../../test/utils";
import { MODE_STYLES } from "../comparison/modes";
import RouteMap from "./RouteMap";

// Leaflet's typings omit the internal initialize() its class system calls.
const polylineProto = L.Polyline.prototype as unknown as {
  initialize: (...args: unknown[]) => void;
};

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

  describe("route lines", () => {
    const line: [number, number][] = [
      [54.355, 18.646],
      [54.36, 18.63],
      [54.371, 18.613],
    ];
    const option = (mode: ModeOption["mode"], geometry: ModeOption["geometry"]): ModeOption => ({
      mode,
      duration_min: 10,
      distance_km: 2,
      cost_pln: 0,
      co2_g: 0,
      is_estimate: geometry === null,
      geometry,
    });

    it("draws one line per mode that has live geometry, in that mode's colour", () => {
      // jsdom has no SVG/canvas rendering, so count Leaflet Polyline instances instead.
      const init = vi.spyOn(polylineProto, "initialize");

      render(
        <RouteMap
          trip={makeTrip()}
          routes={[
            option("walk", line),
            option("bike", line),
            option("transit", null),
            option("car", line),
          ]}
        />,
      );

      expect(init).toHaveBeenCalledTimes(3);
      // react-leaflet applies pathOptions after construction, so read the final options.
      const colours = init.mock.contexts.map((line) => (line as L.Polyline).options.color);
      expect(colours).toEqual([
        MODE_STYLES.walk.color,
        MODE_STYLES.bike.color,
        MODE_STYLES.car.color,
      ]);
    });

    it("draws no lines without routes (e.g. while the comparison loads)", () => {
      const init = vi.spyOn(polylineProto, "initialize");

      render(<RouteMap trip={makeTrip()} />);

      expect(init).not.toHaveBeenCalled();
    });

    it("gives walk and bike different line styles so overlapping routes stay visible", () => {
      const init = vi.spyOn(polylineProto, "initialize");

      render(<RouteMap trip={makeTrip()} routes={[option("walk", line), option("bike", line)]} />);

      const [walk, bike] = init.mock.contexts.map((l) => (l as L.Polyline).options);
      expect(walk.dashArray).not.toEqual(bike.dashArray);
    });

    it("removes the lines when routes go away (switching trips)", () => {
      const onRemove = vi.spyOn(L.Polyline.prototype, "onRemove");
      const { rerender } = render(
        <RouteMap trip={makeTrip()} routes={[option("walk", line), option("car", line)]} />,
      );

      rerender(<RouteMap trip={makeTrip({ id: 2 })} />);

      expect(onRemove).toHaveBeenCalledTimes(2);
    });

    it("fits the view to the routes, not just the endpoints", () => {
      const fitBounds = vi.spyOn(L.Map.prototype, "fitBounds");
      const detour: [number, number][] = [
        [54.355, 18.646],
        [54.5, 18.9], // far outside the start/destination box
        [54.371, 18.613],
      ];

      render(<RouteMap trip={makeTrip()} routes={[option("car", detour)]} />);

      expect(JSON.stringify(fitBounds.mock.lastCall?.[0])).toContain("54.5");
    });

    it("ignores degenerate geometry with fewer than two points", () => {
      const init = vi.spyOn(polylineProto, "initialize");

      render(<RouteMap trip={makeTrip()} routes={[option("walk", []), option("bike", [[54.3, 18.6]])]} />);

      expect(init).not.toHaveBeenCalled();
    });

    it("keeps start/destination markers above route lines that load later", () => {
      // Lines mount after the markers (when the comparison arrives), so plain
      // render order would draw them on top; markers need a higher pane.
      const markerInit = vi.spyOn(
        L.CircleMarker.prototype as unknown as { initialize: (...a: unknown[]) => void },
        "initialize",
      );
      const { container, rerender } = render(<RouteMap trip={makeTrip()} />);
      rerender(<RouteMap trip={makeTrip()} routes={[option("car", line)]} />);

      const markerPanes = markerInit.mock.contexts.map((m) => (m as L.CircleMarker).options.pane);
      expect(markerPanes).toEqual(["endpoints", "endpoints"]);
      const pane = container.querySelector<HTMLElement>(".leaflet-endpoints-pane");
      expect(Number(pane?.style.zIndex)).toBeGreaterThan(400); // overlayPane is 400
    });
  });
});
