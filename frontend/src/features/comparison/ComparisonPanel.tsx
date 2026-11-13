import { ApiError } from "../../lib/api";
import type { ModeOption, Weather } from "../../lib/types";
import {
  describeWeather,
  formatCo2,
  formatCost,
  formatDistance,
  formatDuration,
} from "./format";
import { MODE_STYLES } from "./modes";
import { useComparison, useRecommendation } from "./queries";

interface ComparisonPanelProps {
  tripId: number;
}

export function ComparisonPanel({ tripId }: ComparisonPanelProps) {
  const comparison = useComparison(tripId);
  // Same query as RecommendationCard: shared, one request. Cards don't wait for it.
  const recommended = useRecommendation(tripId).data?.recommended_mode;

  if (comparison.isPending) {
    return (
      <p className="text-sm text-slate-500">
        Comparing ways to get there (routes and weather)…
      </p>
    );
  }

  const data = comparison.data;
  if (!data) {
    // Error with nothing cached to fall back on.
    const gone =
      comparison.error instanceof ApiError && comparison.error.status === 404;
    if (gone) {
      return (
        <p
          role="alert"
          className="rounded-md bg-red-50 p-3 text-sm text-red-700"
        >
          This trip no longer exists.
        </p>
      );
    }
    return (
      <div
        role="alert"
        className="rounded-md bg-red-50 p-3 text-sm text-red-700"
      >
        <p>Couldn't compare this trip: {comparison.error?.message}</p>
        <button
          type="button"
          onClick={() => comparison.refetch()}
          className="mt-2 font-medium underline"
        >
          Try again
        </button>
      </div>
    );
  }

  const { weather, options } = data;
  // Transit is always an estimate (no live timetable); any *other* estimated
  // mode means OSRM failed or timed out for it.
  const routingFellBack = options.some(
    (o) => o.is_estimate && o.mode !== "transit",
  );

  return (
    <div className="space-y-4">
      {comparison.isError && (
        // A background refresh failed; keep showing the last good result.
        <p
          role="alert"
          className="rounded-md bg-amber-50 p-2 text-xs text-amber-800"
        >
          Couldn't refresh the comparison ({comparison.error.message}). Showing
          the last result.
        </p>
      )}
      <WeatherStrip weather={weather} />
      <ul className="grid gap-3 sm:grid-cols-2">
        {options.map((option) => (
          <ModeCard
            key={option.mode}
            option={option}
            recommended={option.mode === recommended}
          />
        ))}
      </ul>
      <div className="space-y-1 text-xs text-slate-500">
        {routingFellBack && (
          <p>
            The live route service was unavailable for some modes, so their
            values are estimates from distance and average speed.
          </p>
        )}
        <p>
          Public transport is estimated from distance (no live timetable).
          Costs: car fuel only, transit single ticket.
        </p>
      </div>
    </div>
  );
}

function WeatherStrip({ weather }: { weather: Weather | null }) {
  if (weather === null) {
    return (
      <p className="rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-600">
        Weather unavailable right now.
      </p>
    );
  }
  const { label, icon } = describeWeather(weather.weather_code);
  return (
    <div
      role="group"
      aria-label="Current weather"
      className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md bg-sky-50 px-3 py-2 text-sm text-sky-900"
    >
      {/* Says "current" up front: the recommendation above may use a forecast. */}
      <span className="font-medium">
        Current weather: <span aria-hidden="true">{icon}</span> {label}
      </span>
      <span>{Math.round(weather.temperature_c)}°C</span>
      <span>Wind {Math.round(weather.wind_speed_kmh)} km/h</span>
      <span>Precipitation {weather.precipitation_mm} mm</span>
      <span className="text-sky-700">at the start</span>
    </div>
  );
}

function ModeCard({
  option,
  recommended,
}: {
  option: ModeOption;
  recommended: boolean;
}) {
  const style = MODE_STYLES[option.mode];
  const approx = option.is_estimate ? "~" : "";
  const headingId = `mode-${option.mode}`;

  return (
    <li
      aria-labelledby={headingId}
      className="rounded-lg border border-slate-200 p-3"
      style={{ borderLeft: `4px solid ${style.color}` }}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 id={headingId} className="font-medium">
          <span aria-hidden="true">{style.icon}</span> {style.label}
          {option.geometry && (
            // Legend for this mode's map line: same colour and dash pattern.
            <svg
              aria-hidden="true"
              width="28"
              height="8"
              className="ml-2 inline-block align-middle"
            >
              <line
                x1="2"
                y1="4"
                x2="26"
                y2="4"
                stroke={style.color}
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={style.dashArray}
              />
            </svg>
          )}
        </h3>
        {recommended && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
            Recommended
          </span>
        )}
        {option.is_estimate && (
          <span
            title="Calculated from distance and average speed, not a live route"
            className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800"
          >
            Estimate
          </span>
        )}
      </div>
      <p className="mt-1 text-2xl font-semibold">
        {approx}
        {formatDuration(option.duration_min)}
      </p>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-slate-500">Distance</dt>
          <dd>
            {approx}
            {formatDistance(option.distance_km)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Cost</dt>
          <dd>{formatCost(option.cost_pln)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">CO₂</dt>
          <dd>{formatCo2(option.co2_g)}</dd>
        </div>
      </dl>
    </li>
  );
}
