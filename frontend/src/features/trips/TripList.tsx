import type { Trip } from "../../lib/types";
import { useDeleteTrip, useTrips } from "./queries";

interface TripListProps {
  selectedTripId: number | null;
  onSelect: (tripId: number | null) => void;
}

export function TripList({ selectedTripId, onSelect }: TripListProps) {
  const trips = useTrips();
  // Hook-level callback (not a per-mutate() one): TanStack runs it for every
  // delete, with this render's selectedTripId, so it is correct even if the user
  // selected the trip while its DELETE was in flight.
  const deletion = useDeleteTrip((deletedId) => {
    if (deletedId === selectedTripId) onSelect(null);
  });

  if (trips.isPending) {
    return <p className="text-sm text-slate-500">Loading trips…</p>;
  }

  if (trips.isError) {
    return (
      <div
        role="alert"
        className="rounded-md bg-red-50 p-3 text-sm text-red-700"
      >
        <p>Couldn't load your trips: {trips.error.message}</p>
        <button
          type="button"
          // With no cached data, TanStack v5 puts the query back into "pending"
          // on refetch, so the loading state above is the retry feedback.
          onClick={() => trips.refetch()}
          className="mt-2 font-medium underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (trips.data.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No trips yet. Add your usual commute above to compare ways to get there.
      </p>
    );
  }

  function handleDelete(trip: Trip) {
    if (!window.confirm(`Delete "${trip.name}"?`)) return;
    deletion.mutate(trip.id);
  }

  return (
    <div>
      {deletion.isError && (
        <p
          role="alert"
          className="mb-2 rounded-md bg-red-50 p-3 text-sm text-red-700"
        >
          Couldn't delete the trip: {deletion.error.message}
        </p>
      )}
      <ul className="divide-y divide-slate-100">
        {trips.data.map((trip) => (
          <TripItem
            key={trip.id}
            trip={trip}
            selected={trip.id === selectedTripId}
            deleting={deletion.isPending && deletion.variables === trip.id}
            // One delete at a time: a second mutate() would take over the shared
            // mutation state and re-enable the first trip's button mid-request.
            deleteDisabled={deletion.isPending}
            onSelect={() => onSelect(trip.id)}
            onDelete={() => handleDelete(trip)}
          />
        ))}
      </ul>
    </div>
  );
}

interface TripItemProps {
  trip: Trip;
  selected: boolean;
  deleting: boolean;
  deleteDisabled: boolean;
  onSelect: () => void;
  onDelete: () => void;
}

function TripItem({
  trip,
  selected,
  deleting,
  deleteDisabled,
  onSelect,
  onDelete,
}: TripItemProps) {
  return (
    <li
      className={`flex items-start gap-2 rounded-md px-2 py-2 ${selected ? "bg-emerald-50" : ""}`}
    >
      <div className="min-w-0 flex-1">
        <button
          type="button"
          aria-pressed={selected}
          onClick={onSelect}
          className="text-left font-medium text-slate-900 hover:underline"
        >
          {trip.name}
        </button>
        <div className="flex items-center gap-2 text-sm text-slate-500">
          {/* Phones wrap the full route (touch has no hover); wider screens cut
              it off with "…" and show the full text on hover. */}
          <p
            className="min-w-0 break-words md:truncate"
            title={`${trip.origin_address} → ${trip.destination_address}`}
          >
            {trip.origin_address} → {trip.destination_address}
          </p>
          {trip.usual_departure_time && (
            // Separate element so truncation never hides it. Backend sends
            // "HH:MM:SS"; minutes are enough here.
            <span className="shrink-0 rounded bg-slate-100 px-1.5 text-xs text-slate-600">
              {trip.usual_departure_time.slice(0, 5)}
            </span>
          )}
        </div>
      </div>
      <button
        type="button"
        onClick={onDelete}
        disabled={deleteDisabled}
        aria-label={`Delete ${trip.name}`}
        className="shrink-0 rounded px-2 py-1 text-sm text-slate-500 hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
      >
        {deleting ? "Deleting…" : "Delete"}
      </button>
    </li>
  );
}
