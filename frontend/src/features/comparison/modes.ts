import type { Mode } from "../../lib/types";

// Shared by the comparison cards and the map lines so colours always match.
// Deliberately not green/red: those are the map's start/destination markers.
// Walk and bike often follow the same streets, so they also get distinct dash
// patterns: the lines stay distinguishable when overlapping, and not by colour alone.
export const MODE_STYLES: Record<
  Mode,
  { label: string; icon: string; color: string; dashArray?: string }
> = {
  walk: { label: "Walk", icon: "🚶", color: "#0d9488", dashArray: "2 8" },
  bike: { label: "Bike", icon: "🚲", color: "#2563eb", dashArray: "12 8" },
  transit: { label: "Public transport", icon: "🚋", color: "#7c3aed" },
  car: { label: "Car", icon: "🚗", color: "#ea580c" },
};
