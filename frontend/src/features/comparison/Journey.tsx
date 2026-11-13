import type { TransitLeg } from "../../lib/types";
import { formatDeparture, formatDuration } from "./format";

// Above this many legs, show a one-line summary instead of every leg.
const MAX_LISTED_LEGS = 4;

function rideLabel(mode: string): { icon: string; label: string } {
  switch (mode) {
    case "WALK":
      return { icon: "🚶", label: "Walk" };
    case "BUS":
      return { icon: "🚌", label: "Bus" };
    case "COACH":
      return { icon: "🚌", label: "Coach" };
    case "TRAM":
      return { icon: "🚋", label: "Tram" };
    case "SUBWAY":
    case "METRO":
      return { icon: "🚇", label: "Metro" };
    case "FERRY":
      return { icon: "⛴️", label: "Ferry" };
    default:
      // REGIONAL_RAIL, LONG_DISTANCE, HIGHSPEED_RAIL, SUBURBAN, NIGHT_RAIL, ...
      return { icon: "🚆", label: "Train" };
  }
}

function rideName(leg: TransitLeg): string {
  const { label } = rideLabel(leg.mode);
  return leg.line ? `${label} ${leg.line}` : label;
}

export function Journey({ legs }: { legs: TransitLeg[] }) {
  const rides = legs.filter((leg) => leg.mode !== "WALK");
  const firstRide = rides[0];

  return (
    <div className="mt-2 space-y-1 text-sm">
      {legs.length <= MAX_LISTED_LEGS ? (
        <ol aria-label="Journey" className="flex flex-wrap items-center gap-1">
          {legs.map((leg, i) => (
            <li key={i} className="flex items-center gap-1">
              {i > 0 && (
                <span aria-hidden="true" className="text-slate-400">
                  →
                </span>
              )}
              <span
                title={leg.headsign ? `towards ${leg.headsign}` : undefined}
                className="rounded bg-slate-100 px-1.5 py-0.5"
              >
                <span aria-hidden="true">{rideLabel(leg.mode).icon}</span>{" "}
                {leg.mode === "WALK" ? (
                  <>
                    {/* The icon is decorative; say the mode for screen readers. */}
                    <span className="sr-only">Walk </span>
                    {formatDuration(leg.duration_min)}
                  </>
                ) : (
                  <>
                    {`${rideName(leg)} · ${formatDuration(leg.duration_min)}`}
                    {leg.headsign && (
                      <span className="sr-only">, towards {leg.headsign}</span>
                    )}
                  </>
                )}
              </span>
            </li>
          ))}
        </ol>
      ) : (
        <JourneySummary rides={rides} />
      )}
      {firstRide && (
        <p className="text-xs text-slate-500">
          Leaves {formatDeparture(firstRide.start_time)} from{" "}
          {firstRide.from_name}
        </p>
      )}
    </div>
  );
}

function JourneySummary({ rides }: { rides: TransitLeg[] }) {
  if (rides.length === 0) return null;
  // The longest ride characterises the journey (e.g. the intercity train).
  const main = rides.reduce((a, b) =>
    b.duration_min > a.duration_min ? b : a,
  );
  const changes = rides.length - 1;
  return (
    <p>
      <span aria-hidden="true">{rideLabel(main.mode).icon}</span>{" "}
      {rideName(main)}
      {" · "}
      {changes === 0
        ? "direct"
        : `${changes} ${changes === 1 ? "change" : "changes"}`}
    </p>
  );
}
