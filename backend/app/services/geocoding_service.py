from app.clients import nominatim
from app.clients.nominatim import GeocodingUnavailableError as GeocodingUnavailableError
from app.clients.schemas import GeocodeResult as GeocodeResult

# GeocodingUnavailableError and GeocodeResult are re-exported so routers depend
# only on this service, not on app.clients directly.


class AddressNotFoundError(Exception):
    def __init__(self, address: str) -> None:
        self.address = address
        super().__init__(f"Address not found: {address}")


def geocode_address(address: str) -> GeocodeResult:
    """Resolve an address to coordinates.

    Raises AddressNotFoundError if Nominatim has no match, and lets
    nominatim.GeocodingUnavailableError propagate if Nominatim itself failed --
    the router maps those to 404 and 503 respectively.

    Called by the frontend when a trip is being saved; the resulting coordinates
    are stored on the Trip, so comparisons never geocode again.
    """
    result = nominatim.geocode(address)
    if result is None:
        raise AddressNotFoundError(address)
    return result
