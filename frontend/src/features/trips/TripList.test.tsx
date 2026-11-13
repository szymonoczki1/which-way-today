import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../lib/api";
import { ApiError } from "../../lib/api";
import { makeTrip, renderWithClient } from "../../test/utils";
import { TripList } from "./TripList";

vi.mock("../../lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../lib/api")>()),
  listTrips: vi.fn(),
  deleteTrip: vi.fn(),
}));

const listTrips = vi.mocked(api.listTrips);
const deleteTrip = vi.mocked(api.deleteTrip);

const HOME_UNI = makeTrip();
const HOME_GYM = makeTrip({
  id: 2,
  name: "Home -> Gym",
  usual_departure_time: null,
});

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("TripList", () => {
  it("shows a loading state", () => {
    listTrips.mockReturnValue(new Promise(() => {}));

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    expect(screen.getByText(/loading trips/i)).toBeInTheDocument();
  });

  it("shows an empty state with a hint", async () => {
    listTrips.mockResolvedValue([]);

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    expect(await screen.findByText(/no trips yet/i)).toBeInTheDocument();
  });

  it("shows an error state with a retry button", async () => {
    listTrips.mockRejectedValueOnce(
      new ApiError(0, "Could not reach the server"),
    );
    listTrips.mockResolvedValueOnce([HOME_UNI]);
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /could not reach the server/i,
    );
    await user.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Home -> Uni")).toBeInTheDocument();
  });

  it("lists trips with route and optional departure time", async () => {
    listTrips.mockResolvedValue([HOME_UNI, HOME_GYM]);

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Gdansk Main Station");
    expect(items[0]).toHaveTextContent("08:00");
    expect(items[0]).not.toHaveTextContent("08:00:00");
    // Missing optional departure time must not render "null" or a stray separator.
    expect(items[1]).not.toHaveTextContent(/null/i);
  });

  it("selects a trip and marks it as selected", async () => {
    listTrips.mockResolvedValue([HOME_UNI, HOME_GYM]);
    const onSelect = vi.fn();
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={2} onSelect={onSelect} />);

    await user.click(
      await screen.findByRole("button", { name: "Home -> Uni" }),
    );
    expect(onSelect).toHaveBeenCalledWith(1);
    expect(screen.getByRole("button", { name: "Home -> Gym" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("deletes a trip, refreshes the list and clears the selection", async () => {
    listTrips.mockResolvedValueOnce([HOME_UNI, HOME_GYM]);
    listTrips.mockResolvedValueOnce([HOME_GYM]);
    deleteTrip.mockResolvedValue(undefined);
    const onSelect = vi.fn();
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={1} onSelect={onSelect} />);

    const item = (await screen.findAllByRole("listitem"))[0];
    await user.click(within(item).getByRole("button", { name: /delete/i }));

    expect(deleteTrip).toHaveBeenCalledWith(1);
    await waitFor(() =>
      expect(screen.getAllByRole("listitem")).toHaveLength(1),
    );
    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("does not delete when the user cancels the confirmation", async () => {
    listTrips.mockResolvedValue([HOME_UNI]);
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: /delete/i }));

    expect(deleteTrip).not.toHaveBeenCalled();
  });

  it("shows an error if deleting fails", async () => {
    listTrips.mockResolvedValue([HOME_UNI]);
    deleteTrip.mockRejectedValue(new ApiError(500, "Internal server error"));
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: /delete/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /couldn't delete.*internal server error/i,
    );
  });

  it("keeps the selection when deleting a different trip", async () => {
    listTrips.mockResolvedValueOnce([HOME_UNI, HOME_GYM]);
    listTrips.mockResolvedValueOnce([HOME_UNI]);
    deleteTrip.mockResolvedValue(undefined);
    const onSelect = vi.fn();
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={1} onSelect={onSelect} />);

    await user.click(
      await screen.findByRole("button", { name: "Delete Home -> Gym" }),
    );

    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(1));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("clears the selection if the trip was selected while its delete was pending", async () => {
    let finishDelete: () => void = () => {};
    listTrips.mockResolvedValueOnce([HOME_UNI, HOME_GYM]);
    listTrips.mockResolvedValueOnce([HOME_GYM]);
    deleteTrip.mockReturnValue(new Promise<void>((resolve) => (finishDelete = resolve)));
    const onSelect = vi.fn();
    const user = userEvent.setup();

    const { rerender } = renderWithClient(
      <TripList selectedTripId={null} onSelect={onSelect} />,
    );
    await user.click(
      await screen.findByRole("button", { name: "Delete Home -> Uni" }),
    );
    // User selects the trip while the DELETE is still in flight.
    rerender(<TripList selectedTripId={1} onSelect={onSelect} />);
    finishDelete();

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(null));
  });

  it("disables every delete button while a delete is in flight", async () => {
    listTrips.mockResolvedValue([HOME_UNI, HOME_GYM]);
    deleteTrip.mockReturnValue(new Promise(() => {}));
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);
    await user.click(
      await screen.findByRole("button", { name: "Delete Home -> Uni" }),
    );

    expect(screen.getByRole("button", { name: "Delete Home -> Uni" })).toHaveTextContent(
      /deleting/i,
    );
    expect(screen.getByRole("button", { name: "Delete Home -> Gym" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Delete Home -> Uni" })).toBeDisabled();
  });

  it("shows the loading state again while retrying", async () => {
    listTrips.mockRejectedValueOnce(new ApiError(0, "Could not reach the server"));
    listTrips.mockReturnValueOnce(new Promise(() => {}));
    const user = userEvent.setup();

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: /try again/i }));

    expect(await screen.findByText(/loading trips/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("drops the deleted trip's cached comparison and recommendation (ids get reused)", async () => {
    listTrips.mockResolvedValueOnce([HOME_UNI]);
    listTrips.mockResolvedValueOnce([]);
    deleteTrip.mockResolvedValue(undefined);
    const user = userEvent.setup();

    const { client } = renderWithClient(
      <TripList selectedTripId={null} onSelect={vi.fn()} />,
    );
    client.setQueryData(["comparison", 1], { trip_id: 1 });
    client.setQueryData(["recommendation", 1], { trip_id: 1 });
    await user.click(await screen.findByRole("button", { name: "Delete Home -> Uni" }));

    await waitFor(() => expect(client.getQueryData(["recommendation", 1])).toBeUndefined());
    expect(client.getQueryData(["comparison", 1])).toBeUndefined();
  });

  it("keeps the departure time visible even when the route is truncated", async () => {
    listTrips.mockResolvedValue([
      makeTrip({
        origin_address: "A very long origin address, Gdańsk, Pomorskie, Polska",
        destination_address: "An even longer destination address, Gdańsk, Polska",
      }),
    ]);

    renderWithClient(<TripList selectedTripId={null} onSelect={vi.fn()} />);

    const item = (await screen.findAllByRole("listitem"))[0];
    // Its own element, not the tail of a line that CSS may cut off with "…".
    expect(within(item).getByText("08:00", { exact: true })).toBeInTheDocument();
    // The full route is still available on hover.
    expect(
      within(item).getByTitle(/A very long origin address.*An even longer destination/),
    ).toBeInTheDocument();
  });
});
