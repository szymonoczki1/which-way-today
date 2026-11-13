from fastapi import APIRouter, HTTPException, Query, status

from app.services.geocoding_service import (
    AddressNotFoundError,
    GeocodeResult,
    GeocodingUnavailableError,
    geocode_address,
)

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("", response_model=GeocodeResult)
def geocode(
    # pattern=r"\S" rejects whitespace-only queries, which min_length alone allows.
    q: str = Query(min_length=1, max_length=200, pattern=r"\S"),
) -> GeocodeResult:
    try:
        return geocode_address(q)
    except AddressNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GeocodingUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoding service is temporarily unavailable, please try again shortly",
        ) from exc
