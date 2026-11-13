import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import type { Recommendation } from "../../lib/types";
import { renderWithClient } from "../../test/utils";
import { RecommendationCard } from "./RecommendationCard";

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  getRecommendation: vi.fn(),
}));

const getRecommendation = vi.mocked(api.getRecommendation);

const RULES: Recommendation = {
  trip_id: 1,
  source: "rules",
  recommended_mode: "transit",
  headline: "Take public transport: ~16 min",
  reasons: [
    "Forecast at 08:00: rain, 6°C, wind 15 km/h, 1.2 mm precipitation.",
    "Too wet for cycling.",
  ],
  weather: {
    temperature_c: 6,
    precipitation_mm: 1.2,
    wind_speed_kmh: 15,
    weather_code: 63,
    time: "2026-11-14T08:00",
    is_forecast: true,
  },
};

describe("RecommendationCard", () => {
  it("shows a loading state", () => {
    getRecommendation.mockReturnValue(new Promise(() => {}));

    renderWithClient(<RecommendationCard tripId={1} />);

    expect(screen.getByText(/working out the best option/i)).toBeInTheDocument();
  });

  it("shows the headline, reasons and a rule-based label", async () => {
    getRecommendation.mockResolvedValue(RULES);

    renderWithClient(<RecommendationCard tripId={1} />);

    const card = await screen.findByRole("region", { name: /recommendation/i });
    expect(card).toHaveTextContent("Take public transport: ~16 min");
    expect(card).toHaveTextContent("Too wet for cycling.");
    expect(card).toHaveTextContent(/rule-based/i);
    expect(getRecommendation).toHaveBeenCalledWith(1, expect.any(AbortSignal));
  });

  it("labels AI answers as AI", async () => {
    getRecommendation.mockResolvedValue({ ...RULES, source: "ai" });

    renderWithClient(<RecommendationCard tripId={1} />);

    const card = await screen.findByRole("region", { name: /recommendation/i });
    expect(within(card).getByText("AI", { exact: true })).toBeInTheDocument();
    expect(card).not.toHaveTextContent(/rule-based/i);
  });

  it("says which hour the weather is for", async () => {
    getRecommendation.mockResolvedValue(RULES);

    renderWithClient(<RecommendationCard tripId={1} />);

    expect(await screen.findByText(/forecast for 08:00/i)).toBeInTheDocument();
  });

  it("says when it used current weather instead of a forecast", async () => {
    getRecommendation.mockResolvedValue({
      ...RULES,
      weather: { ...RULES.weather!, time: null, is_forecast: false },
    });

    renderWithClient(<RecommendationCard tripId={1} />);

    expect(await screen.findByText(/current weather/i)).toBeInTheDocument();
  });

  it("shows an error with retry", async () => {
    getRecommendation.mockRejectedValueOnce(new ApiError(0, "Could not reach the server"));
    getRecommendation.mockResolvedValueOnce(RULES);
    const user = userEvent.setup();

    renderWithClient(<RecommendationCard tripId={1} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(/recommendation/i);
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Take public transport: ~16 min")).toBeInTheDocument();
  });
});
