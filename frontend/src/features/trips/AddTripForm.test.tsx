import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import { makeTrip, renderWithClient } from "../../test/utils";
import { AddTripForm } from "./AddTripForm";

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  geocode: vi.fn(),
  createTrip: vi.fn(),
}));

const geocode = vi.mocked(api.geocode);
const createTrip = vi.mocked(api.createTrip);

const ORIGIN = { lat: 54.355, lon: 18.646, display_name: "Gdańsk Główny" };
const DESTINATION = { lat: 54.371, lon: 18.613, display_name: "Politechnika" };

async function fillForm(
  user: ReturnType<typeof userEvent.setup>,
  values: {
    name?: string;
    origin?: string;
    destination?: string;
    time?: string;
  },
) {
  if (values.name) await user.type(screen.getByLabelText(/name/i), values.name);
  if (values.origin)
    await user.type(screen.getByLabelText(/from/i), values.origin);
  if (values.destination)
    await user.type(screen.getByLabelText(/to/i), values.destination);
  if (values.time)
    await user.type(screen.getByLabelText(/usual departure/i), values.time);
}

const VALID = {
  name: "Home -> Uni",
  origin: "Gdansk Glowny",
  destination: "Politechnika",
};

describe("AddTripForm", () => {
  it("geocodes both addresses, saves the trip with null time, and reports the new id", async () => {
    geocode.mockResolvedValueOnce(ORIGIN).mockResolvedValueOnce(DESTINATION);
    createTrip.mockResolvedValue(makeTrip({ id: 7 }));
    const onCreated = vi.fn();
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={onCreated} />);
    await fillForm(user, VALID);
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(7));
    expect(geocode).toHaveBeenNthCalledWith(1, "Gdansk Glowny");
    expect(geocode).toHaveBeenNthCalledWith(2, "Politechnika");
    expect(createTrip).toHaveBeenCalledWith({
      name: "Home -> Uni",
      origin_address: "Gdansk Glowny",
      origin_lat: 54.355,
      origin_lon: 18.646,
      destination_address: "Politechnika",
      destination_lat: 54.371,
      destination_lon: 18.613,
      // Empty <input type="time"> must become null, not "" (backend 422s on "").
      usual_departure_time: null,
    });
    // Form resets after a successful save.
    expect(screen.getByLabelText(/name/i)).toHaveValue("");
  });

  it("sends the departure time when given", async () => {
    geocode.mockResolvedValueOnce(ORIGIN).mockResolvedValueOnce(DESTINATION);
    createTrip.mockResolvedValue(makeTrip());
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, { ...VALID, time: "07:45" });
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    await waitFor(() => expect(createTrip).toHaveBeenCalled());
    expect(createTrip.mock.calls[0][0].usual_departure_time).toBe("07:45");
  });

  it("geocodes sequentially, not in parallel (backend allows 1 req/s to Nominatim)", async () => {
    let resolveOrigin: (value: typeof ORIGIN) => void = () => {};
    geocode
      .mockReturnValueOnce(new Promise((resolve) => (resolveOrigin = resolve)))
      .mockResolvedValueOnce(DESTINATION);
    createTrip.mockResolvedValue(makeTrip());
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, VALID);
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    await waitFor(() => expect(geocode).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: /saving/i })).toBeDisabled();
    resolveOrigin(ORIGIN);
    await waitFor(() => expect(geocode).toHaveBeenCalledTimes(2));
  });

  it("names the address that was not found (404)", async () => {
    geocode.mockRejectedValueOnce(
      new ApiError(404, "Address not found: Nowhere"),
    );
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, { ...VALID, origin: "Nowhere 123" });
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't find "Nowhere 123"/i);
    expect(createTrip).not.toHaveBeenCalled();
    // Input is kept so the user can fix it.
    expect(screen.getByLabelText(/from/i)).toHaveValue("Nowhere 123");
  });

  it("says lookup is temporarily unavailable on 503, not 'not found'", async () => {
    geocode.mockRejectedValueOnce(new ApiError(503, "Geocoding unavailable"));
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, VALID);
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/temporarily unavailable/i);
    expect(alert).not.toHaveTextContent(/couldn't find/i);
  });

  it("shows the backend message if saving fails", async () => {
    geocode.mockResolvedValueOnce(ORIGIN).mockResolvedValueOnce(DESTINATION);
    createTrip.mockRejectedValue(
      new ApiError(422, "name: String should have at most 100 characters"),
    );
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, VALID);
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /at most 100 characters/i,
    );
  });

  it("rejects whitespace-only fields without calling the API", async () => {
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, {
      name: "   ",
      origin: "   ",
      destination: "Politechnika",
    });
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/fill in/i);
    expect(geocode).not.toHaveBeenCalled();
  });

  it("names the destination when only the destination is not found", async () => {
    geocode
      .mockResolvedValueOnce(ORIGIN)
      .mockRejectedValueOnce(new ApiError(404, "Address not found"));
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await fillForm(user, { ...VALID, destination: "Atlantis 9" });
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/couldn't find "Atlantis 9"/i);
    expect(alert).not.toHaveTextContent(VALID.origin);
    expect(createTrip).not.toHaveBeenCalled();
  });

  it("clears an old validation error on a valid resubmit", async () => {
    let finish: (value: typeof ORIGIN) => void = () => {};
    geocode.mockReturnValueOnce(new Promise((resolve) => (finish = resolve)));
    const user = userEvent.setup();

    renderWithClient(<AddTripForm onCreated={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: /save trip/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/fill in/i);

    await fillForm(user, VALID);
    await user.click(screen.getByRole("button", { name: /save trip/i }));

    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
    finish(ORIGIN);
  });

  it("limits address length to what /geocode accepts", () => {
    renderWithClient(<AddTripForm onCreated={vi.fn()} />);

    expect(screen.getByLabelText(/from/i)).toHaveAttribute("maxLength", "200");
    expect(screen.getByLabelText(/to/i)).toHaveAttribute("maxLength", "200");
  });
});
