import { useRef, useState, type FormEvent } from "react";

import type { TripInput } from "../../lib/types";
import { useCheckRoute, useCreateTrip, type NewTripForm } from "./queries";

interface AddTripFormProps {
  onCreated: (tripId: number) => void;
  /** "Check route": addresses looked up, nothing saved. */
  onChecked?: (route: TripInput) => void;
}

const inputClass =
  "mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500";

function readForm(form: HTMLFormElement): NewTripForm {
  const data = new FormData(form);
  return {
    name: String(data.get("name") ?? "").trim(),
    origin: String(data.get("origin") ?? "").trim(),
    destination: String(data.get("destination") ?? "").trim(),
    departureTime: String(data.get("departureTime") ?? ""),
  };
}

export function AddTripForm({ onCreated, onChecked }: AddTripFormProps) {
  const formRef = useRef<HTMLFormElement>(null);
  const creation = useCreateTrip();
  const check = useCheckRoute();
  const [validationError, setValidationError] = useState<string | null>(null);
  const busy = creation.isPending || check.isPending;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = readForm(form);

    // `required` alone accepts whitespace-only input.
    if (!values.name || !values.origin || !values.destination) {
      setValidationError(
        "Please fill in a name, a starting point and a destination.",
      );
      return;
    }
    setValidationError(null);
    check.reset(); // show only the error of the action just taken

    creation.mutate(values, {
      onSuccess: (trip) => {
        form.reset();
        onCreated(trip.id);
      },
    });
  }

  function handleCheck() {
    if (!formRef.current) return;
    const values = readForm(formRef.current);
    // Checking doesn't need a name; that's only for saving.
    if (!values.origin || !values.destination) {
      setValidationError("Please fill in a starting point and a destination.");
      return;
    }
    setValidationError(null);
    creation.reset();

    // The form keeps its values, so the user can tweak and check again.
    check.mutate(values, { onSuccess: (route) => onChecked?.(route) });
  }

  const failed = check.isError
    ? check.error
    : creation.isError
      ? creation.error
      : null;
  const error = validationError ?? failed?.message ?? null;

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      noValidate
      className="space-y-3"
    >
      <label className="block text-sm font-medium text-slate-700">
        Trip name{" "}
        <span className="font-normal text-slate-400">(only for saving)</span>
        <input
          name="name"
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

      <div className="flex gap-2">
        {onChecked && (
          <button
            type="button"
            onClick={handleCheck}
            disabled={busy}
            className="flex-1 rounded-md border border-emerald-600 px-4 py-2 text-sm font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
          >
            {check.isPending ? "Checking…" : "Check route"}
          </button>
        )}
        <button
          type="submit"
          disabled={busy}
          className="flex-1 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-60"
        >
          {creation.isPending ? "Saving… (looking up addresses)" : "Save trip"}
        </button>
      </div>
    </form>
  );
}
