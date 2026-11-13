from fastapi import APIRouter, Depends, HTTPException, status

from app.models import Trip
from app.repositories.trip_repository import TripRepository, get_trip_repository
from app.schemas import Recommendation, TripComparison, TripCreate, TripRead, TripUpdate
from app.services.comparison_service import get_shared_comparison
from app.services.recommendation_service import recommend_trip
from app.services.trip_service import TripNotFoundError, TripService

router = APIRouter(prefix="/trips", tags=["trips"])


def get_trip_service(repository: TripRepository = Depends(get_trip_repository)) -> TripService:
    return TripService(repository)


@router.get("", response_model=list[TripRead])
def list_trips(service: TripService = Depends(get_trip_service)) -> list[Trip]:
    return service.list_trips()


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(data: TripCreate, service: TripService = Depends(get_trip_service)) -> Trip:
    return service.create_trip(data)


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, service: TripService = Depends(get_trip_service)) -> Trip:
    try:
        return service.get_trip(trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{trip_id}", response_model=TripRead)
def update_trip(
    trip_id: int, data: TripUpdate, service: TripService = Depends(get_trip_service)
) -> Trip:
    try:
        return service.update_trip(trip_id, data)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: int, service: TripService = Depends(get_trip_service)) -> None:
    try:
        service.delete_trip(trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{trip_id}/comparison", response_model=TripComparison)
def get_trip_comparison(
    trip_id: int, service: TripService = Depends(get_trip_service)
) -> TripComparison:
    # Uses the coordinates stored when the trip was saved -- no geocoding here.
    # Always 200 for an existing trip: failed upstreams degrade to estimates.
    try:
        trip = service.get_trip(trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return get_shared_comparison(trip)


@router.get("/{trip_id}/recommendation", response_model=Recommendation)
def get_trip_recommendation(
    trip_id: int, service: TripService = Depends(get_trip_service)
) -> Recommendation:
    # Separate from /comparison so a slow AI call never delays the comparison.
    # Always 200 for an existing trip: no key / AI failure -> rule-based answer.
    try:
        trip = service.get_trip(trip_id)
    except TripNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return recommend_trip(trip)
