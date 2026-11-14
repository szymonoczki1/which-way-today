import { useState, type FormEvent } from "react";

import type { TripInput } from "../../lib/types";
import { useSaveTrip } from "./queries";

interface UnsavedRouteBannerProps {
  route: TripInput;
  /** Suggested name: the form's name, or "From → To". */
  defaultName: string;
  onSaved: (tripId: number) => void;
}

export function UnsavedRouteBanner({
  route,
  defaultName,
  onSaved,
}: UnsavedRouteBannerProps) {
  const save = useSaveTrip();
  const [name, setName] = useState(defaultName.slice(0, 100));
  const trimmed = name.trim();

  function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!trimmed) return;
    // Reuses the coordinates looked up for the check: no second address lookup.
    save.mutate(
      { ...route, name: trimmed },
      { onSuccess: (trip) => onSaved(trip.id) },
    );
  }

  return (
    <form
      onSubmit={handleSave}
      className="flex flex-wrap items-end gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900"
    >
      <p role="status" className="w-full font-medium">
        Not saved yet: this is a one-off check.
      </p>
      <label className="min-w-0 flex-1">
        <span className="block text-xs text-amber-800">Name this trip</span>
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          maxLength={100}
          className="mt-1 w-full rounded-md border border-amber-300 bg-white px-2 py-1"
        />
      </label>
      <button
        type="submit"
        disabled={!trimmed || save.isPending}
        className="rounded-md bg-emerald-600 px-3 py-1.5 font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
      >
        {save.isPending ? "Saving…" : "Save this trip"}
      </button>
      {save.isError && (
        <p role="alert" className="w-full text-red-700">
          Couldn't save: {save.error.message}
        </p>
      )}
    </form>
  );
}
