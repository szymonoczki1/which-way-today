import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  getComparison,
  getRecommendation,
  getRouteComparison,
  getRouteRecommendation,
} from "../../lib/api";
import type { RouteQuery } from "../../lib/types";
import { tripsQueryKey } from "../trips/queries";

/** What to compare: a saved trip (its id) or a route checked without saving. */
export type ComparisonSource = number | RouteQuery;

function routeKey(route: RouteQuery) {
  return [
    "route",
    route.origin_lat,
    route.origin_lon,
    route.destination_lat,
    route.destination_lon,
    route.departure_time,
  ] as const;
}

// Saved trips keep the plain ["comparison", id] key (removed on delete/create).
export const comparisonQueryKey = (source: ComparisonSource) =>
  typeof source === "number"
    ? (["comparison", source] as const)
    : (["comparison", ...routeKey(source)] as const);

export function useComparison(source: ComparisonSource | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: comparisonQueryKey(source ?? -1),
    queryFn: async ({ signal }) => {
      if (typeof source !== "number")
        return getRouteComparison(source!, signal);
      try {
        // signal: abandoned comparisons (clicking through trips) get cancelled.
        return await getComparison(source, signal);
      } catch (error) {
        // 404 = trip deleted elsewhere (another tab, DB reset). Refresh the
        // list so the selection clears, instead of offering a futile retry.
        if (error instanceof ApiError && error.status === 404) {
          void queryClient.invalidateQueries({ queryKey: tripsQueryKey });
        }
        throw error;
      }
    },
    enabled: source !== null,
    // Each comparison costs 5 calls to free, rate-limited upstreams; switching
    // back and forth between trips shouldn't repeat them.
    staleTime: 5 * 60 * 1000,
  });
}

export const recommendationQueryKey = (source: ComparisonSource) =>
  typeof source === "number"
    ? (["recommendation", source] as const)
    : (["recommendation", ...routeKey(source)] as const);

export function useRecommendation(source: ComparisonSource | null) {
  return useQuery({
    queryKey: recommendationQueryKey(source ?? -1),
    queryFn: ({ signal }) =>
      typeof source === "number"
        ? getRecommendation(source, signal)
        : getRouteRecommendation(source!, signal),
    enabled: source !== null,
    // Same upstream cost as the comparison, plus an optional AI call.
    staleTime: 5 * 60 * 1000,
  });
}
