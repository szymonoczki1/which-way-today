import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import type { TripComparison } from "../../lib/types";
import { renderWithClient } from "../../test/utils";
import { ComparisonPanel } from "./ComparisonPanel";

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  getComparison: vi.fn(),
  getRecommendation: vi.fn(),
}));

const getComparison = vi.mocked(api.getComparison);
const getRecommendation = vi.mocked(api.getRecommendation);

const LINE: [number, number][] = [
  [54.35, 18.64],
  [54.37, 18.61],
];

const COMPARISON: TripComparison = {
  trip_id: 1,
  weather: {
    temperature_c: 4.6,
    precipitation_mm: 0.4,
    wind_speed_kmh: 15.7,
    weather_code: 61,
  },
  options: [
    {
      mode: "walk",
      duration_min: 35,
      distance_km: 2.66,
      cost_pln: 0,
      co2_g: 0,
      is_estimate: false,
      geometry: LINE,
    },
    {
      mode: "bike",
      duration_min: 11,
      distance_km: 2.69,
      cost_pln: 0,
      co2_g: 0,
      is_estimate: false,
      geometry: LINE,
    },
    {
      mode: "transit",
      duration_min: 16,
      distance_km: 2.68,
      cost_pln: 4.8,
      co2_g: 161,
      is_estimate: true,
      geometry: null,
    },
    {
      mode: "car",
      duration_min: 5.3,
      distance_km: 2.68,
      cost_pln: 1.21,
      co2_g: 456,
      is_estimate: false,
      geometry: LINE,
    },
  ],
};

function card(mode: RegExp) {
  return screen.getByRole("listitem", { name: mode });
}

describe("ComparisonPanel", () => {
  it("shows a loading state while comparing", () => {
    getComparison.mockReturnValue(new Promise(() => {}));

    renderWithClient(<ComparisonPanel tripId={1} />);

    expect(screen.getByText(/comparing/i)).toBeInTheDocument();
  });

  it("shows one card per mode with time, distance, cost and CO2", async () => {
    getComparison.mockResolvedValue(COMPARISON);

    renderWithClient(<ComparisonPanel tripId={1} />);

    expect(await screen.findAllByRole("listitem")).toHaveLength(4);
    expect(getComparison).toHaveBeenCalledWith(1, expect.anything());
    const walk = card(/walk/i);
    expect(walk).toHaveTextContent("35 min");
    expect(walk).toHaveTextContent("2.7 km");
    expect(walk).toHaveTextContent("Free");
    expect(walk).toHaveTextContent("0 g");
    const car = card(/car/i);
    expect(car).toHaveTextContent("5 min");
    expect(car).toHaveTextContent("1.21 zł");
    expect(car).toHaveTextContent("456 g");
    expect(card(/public transport/i)).toHaveTextContent("4.80 zł");
  });

  it("marks only estimated modes as estimates", async () => {
    getComparison.mockResolvedValue(COMPARISON);

    renderWithClient(<ComparisonPanel tripId={1} />);

    await screen.findAllByRole("listitem");
    expect(within(card(/public transport/i)).getByText(/estimate/i)).toBeInTheDocument();
    expect(card(/public transport/i)).toHaveTextContent("~16 min");
    expect(within(card(/walk/i)).queryByText(/estimate/i)).toBeNull();
    expect(card(/walk/i)).not.toHaveTextContent("~");
  });

  it("explains estimates when the routing service fell back", async () => {
    getComparison.mockResolvedValue({
      ...COMPARISON,
      options: COMPARISON.options.map((o) => ({
        ...o,
        is_estimate: true,
        geometry: null,
      })),
    });

    renderWithClient(<ComparisonPanel tripId={1} />);

    await screen.findAllByRole("listitem");
    expect(
      screen.getByText(/route service.*unavailable/i),
    ).toBeInTheDocument();
  });

  it("shows current weather", async () => {
    getComparison.mockResolvedValue(COMPARISON);

    renderWithClient(<ComparisonPanel tripId={1} />);

    const weather = await screen.findByRole("group", { name: /weather/i });
    expect(weather).toHaveTextContent(/rain/i);
    expect(weather).toHaveTextContent("5°C"); // 4.6 rounded
    expect(weather).toHaveTextContent("16 km/h");
    expect(weather).toHaveTextContent("0.4 mm");
  });

  it("says weather is unavailable when it is null, but still shows the modes", async () => {
    getComparison.mockResolvedValue({ ...COMPARISON, weather: null });

    renderWithClient(<ComparisonPanel tripId={1} />);

    expect(await screen.findByText(/weather unavailable/i)).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
  });

  it("shows an error with retry", async () => {
    getComparison.mockRejectedValueOnce(
      new ApiError(0, "Could not reach the server"),
    );
    getComparison.mockResolvedValueOnce(COMPARISON);
    const user = userEvent.setup();

    renderWithClient(<ComparisonPanel tripId={1} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not reach the server/i,
    );
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findAllByRole("listitem")).toHaveLength(4);
  });

  it("never shows the previous trip's numbers while the next one loads", async () => {
    getComparison.mockResolvedValueOnce(COMPARISON); // trip 1: car 1.21 zł
    getComparison.mockReturnValueOnce(new Promise(() => {})); // trip 2 still loading

    const { rerender } = renderWithClient(<ComparisonPanel tripId={1} />);
    expect(await screen.findByText("1.21 zł")).toBeInTheDocument();
    rerender(<ComparisonPanel tripId={2} />);

    expect(await screen.findByText(/comparing/i)).toBeInTheDocument();
    expect(screen.queryByText("1.21 zł")).toBeNull();
    expect(getComparison).toHaveBeenLastCalledWith(2, expect.anything());
  });

  it("shows the loading state again while retrying", async () => {
    getComparison.mockRejectedValueOnce(new ApiError(0, "Could not reach the server"));
    getComparison.mockReturnValueOnce(new Promise(() => {}));
    const user = userEvent.setup();

    renderWithClient(<ComparisonPanel tripId={1} />);
    await user.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText(/comparing/i)).toBeInTheDocument();
  });

  it("keeps showing the last comparison if a background refresh fails", async () => {
    getComparison.mockResolvedValueOnce(COMPARISON);
    getComparison.mockRejectedValueOnce(new ApiError(0, "Could not reach the server"));

    const { client } = renderWithClient(<ComparisonPanel tripId={1} />);
    await screen.findByText("1.21 zł");
    await client.refetchQueries({ queryKey: ["comparison", 1] });

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't refresh/i);
    expect(screen.getByText("1.21 zł")).toBeInTheDocument();
  });

  it("on 404 (trip deleted elsewhere) refreshes the trip list instead of offering retry", async () => {
    getComparison.mockRejectedValue(new ApiError(404, "Trip 1 not found"));

    const { client } = renderWithClient(<ComparisonPanel tripId={1} />);
    const invalidate = vi.spyOn(client, "invalidateQueries");

    expect(await screen.findByRole("alert")).toHaveTextContent(/no longer exists/i);
    expect(screen.queryByRole("button", { name: /try again/i })).toBeNull();
    await vi.waitFor(() =>
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["trips"] }),
    );
  });

  it("passes an abort signal so abandoned comparisons can be cancelled", async () => {
    getComparison.mockResolvedValue(COMPARISON);

    renderWithClient(<ComparisonPanel tripId={1} />);
    await screen.findByText("1.21 zł");

    expect(getComparison.mock.calls[0][1]).toBeInstanceOf(AbortSignal);
  });

  it("describes fallback values as distance-based estimates", async () => {
    getComparison.mockResolvedValue({
      ...COMPARISON,
      options: COMPARISON.options.map((o) => ({ ...o, is_estimate: true, geometry: null })),
    });

    renderWithClient(<ComparisonPanel tripId={1} />);

    expect(await screen.findByText(/route service was unavailable/i)).toHaveTextContent(
      /distance and average speed/i,
    );
  });

  it("marks the recommended mode once the recommendation arrives", async () => {
    getComparison.mockResolvedValue(COMPARISON);
    getRecommendation.mockResolvedValue({
      trip_id: 1,
      source: "rules",
      recommended_mode: "bike",
      headline: "Take the bike: 11 min",
      reasons: ["x"],
      weather: null,
    });

    renderWithClient(<ComparisonPanel tripId={1} />);

    await screen.findAllByRole("listitem");
    expect(await within(card(/bike/i)).findByText(/recommended/i)).toBeInTheDocument();
    expect(within(card(/car/i)).queryByText(/recommended/i)).toBeNull();
  });

  it("shows the cards even if the recommendation is still loading", async () => {
    getComparison.mockResolvedValue(COMPARISON);
    getRecommendation.mockReturnValue(new Promise(() => {}));

    renderWithClient(<ComparisonPanel tripId={1} />);

    expect(await screen.findAllByRole("listitem")).toHaveLength(4);
    expect(screen.queryByText(/recommended/i)).toBeNull();
  });

  it("labels the weather strip as current weather (the recommendation may use a forecast)", async () => {
    getComparison.mockResolvedValue(COMPARISON);

    renderWithClient(<ComparisonPanel tripId={1} />);

    const weather = await screen.findByRole("group", { name: /current weather/i });
    expect(weather).toHaveTextContent(/^current weather/i);
  });
});
