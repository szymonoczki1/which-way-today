import type { RecommendationWeather } from "../../lib/types";
import { MODE_STYLES } from "./modes";
import { useRecommendation } from "./queries";

interface RecommendationCardProps {
  tripId: number;
}

export function RecommendationCard({ tripId }: RecommendationCardProps) {
  const recommendation = useRecommendation(tripId);

  if (recommendation.isPending) {
    return (
      <p className="rounded-lg border border-dashed border-slate-300 p-3 text-sm text-slate-500">
        Working out the best option for you…
      </p>
    );
  }

  const data = recommendation.data;
  if (!data) {
    // Non-blocking: the comparison below is still useful on its own.
    return (
      <div
        role="alert"
        className="rounded-md bg-amber-50 p-3 text-sm text-amber-800"
      >
        <p>Couldn't get a recommendation: {recommendation.error?.message}</p>
        <button
          type="button"
          onClick={() => recommendation.refetch()}
          className="mt-1 font-medium underline"
        >
          Try again
        </button>
      </div>
    );
  }

  const style = MODE_STYLES[data.recommended_mode];
  return (
    <section
      aria-label="Recommendation"
      className="rounded-lg border border-emerald-200 bg-emerald-50 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-lg font-semibold text-emerald-900">
          <span aria-hidden="true">{style.icon}</span> {data.headline}
        </p>
        <span
          title={
            data.source === "ai"
              ? "Written by an AI model from the numbers below"
              : "Deterministic rules (no AI key set, or the AI was unavailable)"
          }
          className="rounded-full bg-white px-2 py-0.5 text-xs text-emerald-800 ring-1 ring-emerald-200"
        >
          {data.source === "ai" ? "AI" : "Rule-based"}
        </span>
      </div>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-emerald-900">
        {data.reasons.map((reason, i) => (
          <li key={i}>{reason}</li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-emerald-700">
        {weatherNote(data.weather)}
      </p>
    </section>
  );
}

function weatherNote(weather: RecommendationWeather | null): string {
  if (weather === null) return "No weather data was available.";
  if (weather.is_forecast && weather.time) {
    return `Based on the forecast for ${weather.time.slice(11, 16)} on ${weather.time.slice(0, 10)}.`;
  }
  return "Based on current weather (no usual departure time set, or no forecast available).";
}
