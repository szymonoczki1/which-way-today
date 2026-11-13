import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  createTrip,
  deleteTrip,
  geocode,
  listTrips,
} from "../../lib/api";
import type { GeocodeResult } from "../../lib/types";

export const tripsQueryKey = ["trips"] as const;

export function useTrips() {
  return useQuery({ queryKey: tripsQueryKey, queryFn: listTrips });
}

export function useDeleteTrip(onDeleted?: (tripId: number) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (tripId: number) => deleteTrip(tripId),
    onSuccess: (_data, tripId) => {
      onDeleted?.(tripId);
      return queryClient.invalidateQueries({ queryKey: tripsQueryKey });
    },
  });
}

export interface NewTripForm {
  name: string;
  origin: string;
  destination: string;
  /** Raw <input type="time"> value: "HH:MM" or "" when left empty. */
  departureTime: string;
}

/** Geocode, turning API errors into messages that name the address. */
async function locate(address: string): Promise<GeocodeResult> {
  try {
    return await geocode(address);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      throw new Error(
        `We couldn't find "${address}". Try a more specific address.`,
      );
    }
    if (error instanceof ApiError && error.status === 503) {
      throw new Error(
        "Address lookup is temporarily unavailable. Please try again in a moment.",
      );
    }
    throw error;
  }
}

export function useCreateTrip() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (form: NewTripForm) => {
      // Geocode once, here, and store the coordinates: comparisons never
      // re-geocode. Sequential on purpose: the backend spaces Nominatim calls
      // 1 s apart anyway, and this way a bad origin fails before we spend a
      // request on the destination.
      const origin = await locate(form.origin);
      const destination = await locate(form.destination);
      return createTrip({
        name: form.name,
        origin_address: form.origin,
        origin_lat: origin.lat,
        origin_lon: origin.lon,
        destination_address: form.destination,
        destination_lat: destination.lat,
        destination_lon: destination.lon,
        usual_departure_time: form.departureTime || null,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: tripsQueryKey }),
  });
}
