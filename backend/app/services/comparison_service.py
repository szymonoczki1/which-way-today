"""Compare walk / bike / transit / car for a saved trip.

Live data: OSRM routes (walk, bike, car) and Open-Meteo current weather, fetched
concurrently under one overall deadline. Anything that fails or misses the
deadline falls back to the static factors below, so the endpoint always answers.
"""

import logging
import math
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait

from app.clients import open_meteo, osrm
from app.clients.schemas import RouteResult
from app.models import Trip
from app.schemas import ModeOption, TripComparison

logger = logging.getLogger(__name__)

# Overall budget for all upstream calls. The client timeouts are per-operation
# (connect 3 s, then 5 s per read), not a total cap, so this is what actually
# bounds the endpoint's response time.
DEADLINE_S = 6.0

# One shared, capped pool: a thread that misses the deadline can't be killed and
# keeps running until its HTTP call ends, so a per-request pool would let threads
# pile up without limit while an upstream is degraded. 16 = 4 concurrent comparisons.
_executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="comparison")

# --- Static factors (MVP assumptions; documented so they can be defended/updated) ---

# Straight-line distance x this factor approximates street-network distance
# when OSRM is unavailable (typical urban detour ratio is ~1.2-1.4).
DETOUR_FACTOR = 1.3
# Fallback average speeds when OSRM is unavailable.
WALK_SPEED_KMH = 5.0
BIKE_SPEED_KMH = 15.0
CAR_SPEED_KMH = 35.0  # urban average incl. lights/junctions, no live traffic

# Public transport has no live routing in the MVP: always estimated from the
# car route distance (transit follows roads/tracks roughly like a car does).
TRANSIT_SPEED_KMH = 20.0  # average in-vehicle speed for urban tram/bus
TRANSIT_OVERHEAD_MIN = 8.0  # walking to/from stops + average wait
TRANSIT_TICKET_PLN = 4.80  # ZTM Gdansk normal (full-price) single ticket; confirmed 2026-11
TRANSIT_CO2_G_PER_KM = 60.0  # per passenger-km, mixed tram/bus average

CAR_COST_PLN_PER_KM = 0.45  # fuel only: ~7 L/100 km x ~6.4 PLN/L
CAR_CO2_G_PER_KM = 170.0  # average real-world passenger car, single occupant


# /comparison and /recommendation are requested together for the same trip view.
# Sharing one computation keeps their numbers identical (no badge on a card the
# recommendation's own numbers wouldn't pick) and halves upstream calls. Keyed by
# id *and* coordinates, since SQLite can reuse a deleted trip's id.
SHARED_TTL_S = 60.0
_shared: dict[tuple[int, float, float, float, float], tuple[float, Future[TripComparison]]] = {}
_shared_lock = threading.Lock()


def get_shared_comparison(trip: Trip) -> TripComparison:
    """compare_trip, but concurrent/recent calls for the same trip share one result."""
    assert trip.id is not None, "only saved trips can be compared"
    key = (trip.id, trip.origin_lat, trip.origin_lon, trip.destination_lat, trip.destination_lon)
    now = time.monotonic()
    with _shared_lock:
        for stale in [k for k, (at, _) in _shared.items() if now - at > SHARED_TTL_S]:
            del _shared[stale]
        entry = _shared.get(key)
        if entry is not None:
            future, owner = entry[1], False
        else:
            future, owner = Future(), True
            _shared[key] = (now, future)

    if owner:
        try:
            future.set_result(compare_trip(trip))
        except BaseException as exc:
            future.set_exception(exc)
            with _shared_lock:
                _shared.pop(key, None)
    # Waiters block at most as long as the owner's compare_trip (its own deadline).
    return future.result()


def compare_trip(trip: Trip, deadline_s: float = DEADLINE_S) -> TripComparison:
    assert trip.id is not None, "only saved trips can be compared"

    route_futures = {
        profile: _executor.submit(
            osrm.get_route,
            trip.origin_lat,
            trip.origin_lon,
            trip.destination_lat,
            trip.destination_lon,
            profile,
        )
        for profile in ("walking", "cycling", "driving")
    }
    weather_future = _executor.submit(
        open_meteo.get_current_weather, trip.origin_lat, trip.origin_lon
    )
    futures = [*route_futures.values(), weather_future]
    wait(futures, timeout=deadline_s)
    for future in futures:
        # Drops calls still queued behind other requests; running ones can't be
        # stopped and just finish in the background (their result is ignored).
        future.cancel()

    walk_route = _result_or_none(route_futures["walking"], "walking route")
    bike_route = _result_or_none(route_futures["cycling"], "cycling route")
    car_route = _result_or_none(route_futures["driving"], "driving route")
    weather = _result_or_none(weather_future, "weather")

    crow_km = _haversine_km(
        trip.origin_lat, trip.origin_lon, trip.destination_lat, trip.destination_lon
    )
    car = _route_option(
        "car", car_route, crow_km, CAR_SPEED_KMH, CAR_COST_PLN_PER_KM, CAR_CO2_G_PER_KM
    )

    transit_km = car.distance_km
    transit = ModeOption(
        mode="transit",
        duration_min=round(transit_km / TRANSIT_SPEED_KMH * 60 + TRANSIT_OVERHEAD_MIN, 1),
        distance_km=transit_km,
        cost_pln=TRANSIT_TICKET_PLN,
        co2_g=round(transit_km * TRANSIT_CO2_G_PER_KM),
        is_estimate=True,
    )

    return TripComparison(
        trip_id=trip.id,
        weather=weather,
        options=[
            _route_option("walk", walk_route, crow_km, WALK_SPEED_KMH, 0.0, 0.0),
            _route_option("bike", bike_route, crow_km, BIKE_SPEED_KMH, 0.0, 0.0),
            transit,
            car,
        ],
    )


def _route_option(
    mode: str,
    route: RouteResult | None,
    crow_km: float,
    fallback_speed_kmh: float,
    cost_pln_per_km: float,
    co2_g_per_km: float,
) -> ModeOption:
    if route is not None:
        distance_km = route.distance_m / 1000
        duration_min = route.duration_s / 60
    else:
        distance_km = crow_km * DETOUR_FACTOR
        duration_min = distance_km / fallback_speed_kmh * 60

    # Round once and derive cost/CO2 from the rounded value, so the numbers the
    # frontend sees are consistent with each other (and with transit's).
    distance_km = round(distance_km, 2)
    return ModeOption(
        mode=mode,  # type: ignore[arg-type]
        duration_min=round(duration_min, 1),
        distance_km=distance_km,
        cost_pln=round(distance_km * cost_pln_per_km, 2),
        co2_g=round(distance_km * co2_g_per_km),
        is_estimate=route is None,
        geometry=route.geometry if route is not None else None,
    )


def _result_or_none[T](future: Future[T], label: str) -> T | None:
    if not future.done():
        logger.warning("%s missed the comparison deadline; using fallback", label)
        return None
    try:
        return future.result()
    except Exception:
        # Clients already return None on known failures; this guards against
        # anything unexpected so one bad upstream can't 500 the whole comparison.
        logger.exception("%s raised unexpectedly; using fallback", label)
        return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_km * math.asin(math.sqrt(a))
