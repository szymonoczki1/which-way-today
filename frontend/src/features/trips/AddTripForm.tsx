import { useState, type FormEvent } from "react";

import { useCreateTrip } from "./queries";

interface AddTripFormProps {
  onCreated: (tripId: number) => void;
}

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";

export function AddTripForm({ onCreated }: AddTripFormProps) {
  const creation = useCreateTrip();
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const values = {
      name: String(data.get("name") ?? "").trim(),
      origin: String(data.get("origin") ?? "").trim(),
      destination: String(data.get("destination") ?? "").trim(),
      departureTime: String(data.get("departureTime") ?? ""),
    };

    // `required` alone accepts whitespace-only input.
    if (!values.name || !values.origin || !values.destination) {
      setValidationError(
        "Please fill in a name, a starting point and a destination.",
      );
      return;
    }
    setValidationError(null);

    creation.mutate(values, {
      onSuccess: (trip) => {
        form.reset();
        onCreated(trip.id);
      },
    });
  }

  const error =
    validationError ?? (creation.isError ? creation.error.message : null);

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-3">
      <label className="block text-sm font-medium text-slate-700">
        Trip name
        <input
          name="name"
          required
          maxLength={100}
          placeholder="Home → University"
          className={inputClass}
        />
      </label>
      <label className="block text-sm font-medium text-slate-700">
        From
        <input
          name="origin"
          required
          maxLength={200}
          placeholder="Address or place"
          autoComplete="street-address"
          className={inputClass}
        />
      </label>
      <label className="block text-sm font-medium text-slate-700">
        To
        <input
          name="destination"
          required
          maxLength={200}
          placeholder="Address or place"
          className={inputClass}
        />
      </label>
      <label className="block text-sm font-medium text-slate-700">
        Usual departure time{" "}
        <span className="font-normal text-slate-400">(optional)</span>
        <input name="departureTime" type="time" className={inputClass} />
      </label>

      {error && (
        <p
          role="alert"
          className="rounded-md bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={creation.isPending}
        className="w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
      >
        {creation.isPending ? "Saving… (looking up addresses)" : "Save trip"}
      </button>
    </form>
  );
}
