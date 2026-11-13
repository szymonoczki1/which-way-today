import { useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, getComparison, getRecommendation } from "../../lib/api";
import { tripsQueryKey } from "../trips/queries";

export const comparisonQueryKey = (tripId: number) =>
  ["comparison", tripId] as const;

export function useComparison(tripId: number | null) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: comparisonQueryKey(tripId ?? -1),
    queryFn: async ({ signal }) => {
      try {
        // signal: abandoned comparisons (clicking through trips) get cancelled.
        return await getComparison(tripId!, signal);
      } catch (error) {
        // 404 = trip deleted elsewhere (another tab, DB reset). Refresh the
        // list so the selection clears, instead of offering a futile retry.
        if (error instanceof ApiError && error.status === 404) {
          void queryClient.invalidateQueries({ queryKey: tripsQueryKey });
        }
        throw error;
      }
    },
    enabled: tripId !== null,
    // Each comparison costs 5 calls to free, rate-limited upstreams; switching
    // back and forth between trips shouldn't repeat them.
    staleTime: 5 * 60 * 1000,
  });
}

export const recommendationQueryKey = (tripId: number) =>
  ["recommendation", tripId] as const;

export function useRecommendation(tripId: number | null) {
  return useQuery({
    queryKey: recommendationQueryKey(tripId ?? -1),
    queryFn: ({ signal }) => getRecommendation(tripId!, signal),
    enabled: tripId !== null,
    // Same upstream cost as the comparison, plus an optional AI call.
    staleTime: 5 * 60 * 1000,
  });
}
