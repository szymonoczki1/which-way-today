from fastapi import Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models import Trip


class TripRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[Trip]:
        return list(self.session.exec(select(Trip)).all())

    def get(self, trip_id: int) -> Trip | None:
        return self.session.get(Trip, trip_id)

    def create(self, trip: Trip) -> Trip:
        self.session.add(trip)
        self.session.commit()
        self.session.refresh(trip)
        return trip

    def save(self, trip: Trip) -> Trip:
        self.session.add(trip)
        self.session.commit()
        self.session.refresh(trip)
        return trip

    def delete(self, trip: Trip) -> None:
        self.session.delete(trip)
        self.session.commit()


def get_trip_repository(session: Session = Depends(get_session)) -> TripRepository:
    return TripRepository(session)
