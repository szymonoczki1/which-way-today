"""Check a route without saving it.

Same comparison and recommendation as for a saved trip (GET /trips/{id}/...), from
coordinates in the query string; nothing is written to the database. The frontend
geocodes the addresses first (GET /geocode), as it does when saving a trip.
"""

from datetime import time

from fastapi import APIRouter, Depends, Query

from app.models import Trip
from app.schemas import Recommendation, TripComparison
from app.services.comparison_service import get_shared_comparison
from app.services.recommendation_service import recommend_trip

router = APIRouter(prefix="/routes", tags=["routes"])


def unsaved_route(
    origin_lat: float = Query(ge=-90, le=90),
    origin_lon: float = Query(ge=-180, le=180),
    destination_lat: float = Query(ge=-90, le=90),
    destination_lon: float = Query(ge=-180, le=180),
    # "HH:MM" (or "HH:MM:SS") Gdańsk wall-clock time; omitted = leave now. Strict on
    # purpose: a UTC offset like "08:00Z" would otherwise be accepted and ignored.
    departure_time: str | None = Query(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d(:[0-5]\d)?$"),
) -> Trip:
    # An unsaved Trip (id None): the services only need coordinates and the time.
    return Trip(
        name="",
        origin_address="",
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_address="",
        destination_lat=destination_lat,
        destination_lon=destination_lon,
        usual_departure_time=time.fromisoformat(departure_time) if departure_time else None,
    )


@router.get("/comparison", response_model=TripComparison)
def route_comparison(route: Trip = Depends(unsaved_route)) -> TripComparison:
    # Always 200 for valid input: failed upstreams degrade to estimates.
    return get_shared_comparison(route)


@router.get("/recommendation", response_model=Recommendation)
def route_recommendation(route: Trip = Depends(unsaved_route)) -> Recommendation:
    return recommend_trip(route)
