import logging
from typing import Literal

import httpx
from pydantic import ValidationError

from app.clients.schemas import RouteResult

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# OSRM's public servers use their own profile vocabulary, not our mode names --
# the comparison service (app/services) maps walk/bike/car to these.
OsrmProfile = Literal["driving", "walking", "cycling"]

# router.project-osrm.org only loads the car profile and ignores the profile
# segment, so walking/cycling would silently return car routes. The FOSSGIS
# servers host one profile per path prefix (the "driving" segment is ignored there).
BASE_URLS: dict[OsrmProfile, str] = {
    "driving": "https://router.project-osrm.org/route/v1/driving",
    "walking": "https://routing.openstreetmap.de/routed-foot/route/v1/driving",
    "cycling": "https://routing.openstreetmap.de/routed-bike/route/v1/driving",
}


def get_route(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    profile: OsrmProfile,
) -> RouteResult | None:
    # OSRM expects lon,lat. Fixed-point formatting avoids str() producing "1e-05".
    url = (
        f"{BASE_URLS[profile]}/"
        f"{origin_lon:.6f},{origin_lat:.6f};{destination_lon:.6f},{destination_lat:.6f}"
    )

    try:
        response = httpx.get(
            url,
            params={"overview": "full", "geometries": "geojson"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        routes = data.get("routes")
        if data.get("code") != "Ok" or not routes:
            return None

        route = routes[0]
        # GeoJSON coordinates are [lon, lat]; flip to [lat, lon] for Leaflet.
        geometry = [[lat, lon] for lon, lat in route["geometry"]["coordinates"]]
        return RouteResult(
            distance_m=route["distance"], duration_s=route["duration"], geometry=geometry
        )
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        ValidationError,
    ):
        # ValueError also covers json.JSONDecodeError; AttributeError covers a
        # non-dict JSON body (e.g. a bare list) hitting data.get().
        logger.warning("OSRM %s route failed: %s", profile, url, exc_info=True)
        return None
