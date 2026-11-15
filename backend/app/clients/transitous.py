"""Public transport journeys from Transitous (https://transitous.org).

Free, keyless, community-run MOTIS journey planner over open GTFS timetables.
Usage policy: descriptive User-Agent with contact, visible attribution
(transitous.org/sources, shown in the frontend), and light use (they flag more
than ~720 /plan requests a day; we make one per trip comparison, shared/cached).
"""

import logging
import math
from datetime import UTC, datetime

import httpx
from pydantic import ValidationError

from app.clients.schemas import TransitJourney, TransitLeg

logger = logging.getLogger(__name__)

URL = "https://api.transitous.org/api/v6/plan"
USER_AGENT = "which-way-today/1.0 (+https://github.com/szymonoczki1/which-way-today)"
# Below the comparison's 6 s deadline: a straggler shouldn't hold a pool worker long.
TIMEOUT = httpx.Timeout(4.0, connect=2.0)


def plan(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    *,
    depart_at: datetime,
) -> TransitJourney | None:
    """Best (earliest-arriving) public transport journey, or None on any failure.

    All transit modes (Transitous default): buses, trams, regional and long-distance rail.
    """
    try:
        response = httpx.get(
            URL,
            params={
                "fromPlace": f"{origin_lat:.6f},{origin_lon:.6f}",
                "toPlace": f"{destination_lat:.6f},{destination_lon:.6f}",
                "time": depart_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        itineraries = response.json()["itineraries"]
        if not itineraries:
            return None
        # Earliest arrival (as instants, not strings); fewer changes breaks ties.
        best = min(itineraries, key=lambda it: (_parse(it["endTime"]), it.get("transfers", 0)))
        return TransitJourney(
            duration_min=best["duration"] / 60,
            transfers=best.get("transfers", 0),
            start_time=_utc_iso(best["startTime"]),
            end_time=_utc_iso(best["endTime"]),
            legs=[_leg(raw) for raw in best["legs"]],
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
        # ValueError covers JSON decode errors; the rest cover unexpected shapes.
        logger.warning("Transitous plan failed; using the transit estimate", exc_info=True)
        return None


def _leg(raw: dict) -> TransitLeg:
    geometry_raw = raw.get("legGeometry") or {}
    geometry = decode_polyline(geometry_raw.get("points", ""), geometry_raw.get("precision", 6))
    # Walk legs report a distance (m); ride legs don't, so measure along the line.
    if raw.get("distance") is not None:
        distance_km = raw["distance"] / 1000
    else:
        distance_km = sum(_haversine_km(a, b) for a, b in zip(geometry, geometry[1:], strict=False))
    return TransitLeg(
        mode=raw["mode"],
        line=raw.get("routeShortName"),
        headsign=raw.get("headsign"),
        agency=raw.get("agencyName"),
        from_name=(raw.get("from") or {}).get("name", ""),
        to_name=(raw.get("to") or {}).get("name", ""),
        start_time=_utc_iso(raw["startTime"]),
        end_time=_utc_iso(raw["endTime"]),
        duration_min=raw["duration"] / 60,
        distance_km=distance_km,
        geometry=geometry,
    )


def _parse(timestamp: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without a timezone: {timestamp!r}")
    return parsed


def _utc_iso(timestamp: str) -> str:
    """Validate and normalise to "2026-11-14T07:04:00Z" (raises ValueError if bad)."""
    return _parse(timestamp).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def decode_polyline(encoded: str, precision: int = 6) -> list[list[float]]:
    """Decode a Google encoded polyline into [[lat, lon], ...].

    Raises ValueError/IndexError on malformed input rather than returning
    garbage coordinates (which would corrupt distances and CO2)."""
    factor = 10**precision
    points: list[list[float]] = []
    index = lat = lon = 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                if not 0 <= byte <= 63:
                    raise ValueError("invalid character in encoded polyline")
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append([lat / factor, lon / factor])
    return points


def _haversine_km(a: list[float], b: list[float]) -> float:
    phi1, phi2 = math.radians(a[0]), math.radians(b[0])
    d_phi, d_lambda = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))
