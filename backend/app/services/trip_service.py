from app.models import Trip
from app.repositories.trip_repository import TripRepository
from app.schemas import TripCreate, TripUpdate


class TripNotFoundError(Exception):
    def __init__(self, trip_id: int) -> None:
        self.trip_id = trip_id
        super().__init__(f"Trip {trip_id} not found")


class TripService:
    """Business logic for trips. Deliberately has no FastAPI import: it should
    be testable by handing it a repository directly, with no HTTP layer involved."""

    def __init__(self, repository: TripRepository) -> None:
        self.repository = repository

    def list_trips(self) -> list[Trip]:
        return self.repository.list()

    def get_trip(self, trip_id: int) -> Trip:
        trip = self.repository.get(trip_id)
        if trip is None:
            raise TripNotFoundError(trip_id)
        return trip

    def create_trip(self, data: TripCreate) -> Trip:
        trip = Trip(**data.model_dump())
        return self.repository.create(trip)

    def update_trip(self, trip_id: int, data: TripUpdate) -> Trip:
        trip = self.get_trip(trip_id)
        for field, value in data.model_dump().items():
            setattr(trip, field, value)
        return self.repository.save(trip)

    def delete_trip(self, trip_id: int) -> None:
        trip = self.get_trip(trip_id)
        self.repository.delete(trip)
