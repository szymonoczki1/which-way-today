"""Compare walk / bike / transit / car for a saved trip.

Live data: OSRM routes (walk, bike, car), a Transitous public transport
journey and Open-Meteo current weather, fetched concurrently under one overall
deadline. Anything that fails or misses the deadline falls back to the static
factors below, so the endpoint always answers.
"""

import logging
import math
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime, timedelta
from datetime import time as clock_time
from zoneinfo import ZoneInfo

from app.clients import open_meteo, osrm, transitous
from app.clients.schemas import RouteResult, TransitJourney
from app.models import Trip
from app.schemas import ModeOption, TripComparison

logger = logging.getLogger(__name__)

# Overall budget for all upstream calls. The client timeouts are per-operation
# (connect 3 s, then 5 s per read), not a total cap, so this is what actually
# bounds the endpoint's response time.
DEADLINE_S = 6.0

# One shared, capped pool: a thread that misses the deadline can't be killed and
# keeps running until its HTTP call ends, so a per-request pool would let threads
# pile up without limit while an upstream is degraded. 5 calls per comparison
# (3 routes, weather, transit), so 20 = 4 concurrent comparisons.
_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix="comparison")

# --- Static factors (MVP assumptions; documented so they can be defended/updated) ---

# Straight-line distance x this factor approximates street-network distance
# when OSRM is unavailable (typical urban detour ratio is ~1.2-1.4).
DETOUR_FACTOR = 1.3
# Fallback average speeds when OSRM is unavailable.
WALK_SPEED_KMH = 5.0
BIKE_SPEED_KMH = 15.0
CAR_SPEED_KMH = 35.0  # urban average incl. lights/junctions, no live traffic

# Public transport: a real Transitous journey when available. If not (failure,
# timeout, no connection), estimated from the car route distance.
TRANSIT_SPEED_KMH = 20.0  # estimate: average in-vehicle speed for urban tram/bus
TRANSIT_OVERHEAD_MIN = 8.0  # estimate: walking to/from stops + average wait
TRANSIT_TICKET_PLN = 4.80  # ZTM Gdansk normal (full-price) single ticket; confirmed 2026-11
TRANSIT_CO2_G_PER_KM = 60.0  # estimate: per passenger-km, mixed tram/bus average
# A real journey shows a price only for one ride with ZTM Gdańsk (the single ticket
# above). Changes need a time ticket, and other operators have their own fares.
ZTM_GDANSK_AGENCY = "Zarząd Transportu Miejskiego w Gdańsku"
# Per passenger-km by Transitous mode (typical averages; rail is mostly electric).
TRANSIT_CO2_G_PER_KM_BY_MODE = {
    "BUS": 70.0,
    "COACH": 30.0,
    "TRAM": 40.0,
    "SUBWAY": 35.0,
    "METRO": 35.0,
    "SUBURBAN": 35.0,
    "RAIL": 35.0,
    "REGIONAL_RAIL": 35.0,
    "REGIONAL_FAST_RAIL": 35.0,
    "LONG_DISTANCE": 35.0,
    "HIGHSPEED_RAIL": 35.0,
    "NIGHT_RAIL": 35.0,
    "FERRY": 120.0,
}
NON_RIDE_MODES = {"WALK", "BIKE", "CAR"}

# Trips are local to Gdańsk; departure times are wall-clock times there.
LOCAL_TZ = ZoneInfo("Europe/Warsaw")

CAR_COST_PLN_PER_KM = 0.45  # fuel only: ~7 L/100 km x ~6.4 PLN/L
CAR_CO2_G_PER_KM = 170.0  # average real-world passenger car, single occupant


# /comparison and /recommendation are requested together for the same trip view.
# Sharing one computation keeps their numbers identical (no badge on a card the
# recommendation's own numbers wouldn't pick) and halves upstream calls. Keyed by
# id, coordinates *and* departure time, since SQLite can reuse a deleted trip's id
# and the transit journey depends on when you leave.
SHARED_TTL_S = 60.0
_shared: dict[tuple[object, ...], tuple[float, Future[TripComparison]]] = {}
_shared_lock = threading.Lock()


def get_shared_comparison(trip: Trip) -> TripComparison:
    """compare_trip, but concurrent/recent calls for the same trip share one result."""
    assert trip.id is not None, "only saved trips can be compared"
    key = (
        trip.id,
        trip.origin_lat,
        trip.origin_lon,
        trip.destination_lat,
        trip.destination_lon,
        trip.usual_departure_time,
    )
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
    depart_at = next_departure_utc(trip.usual_departure_time)
    transit_future = _executor.submit(
        transitous.plan,
        trip.origin_lat,
        trip.origin_lon,
        trip.destination_lat,
        trip.destination_lon,
        depart_at=depart_at,
    )
    futures = [*route_futures.values(), weather_future, transit_future]
    wait(futures, timeout=deadline_s)
    for future in futures:
        # Drops calls still queued behind other requests; running ones can't be
        # stopped and just finish in the background (their result is ignored).
        future.cancel()

    walk_route = _result_or_none(route_futures["walking"], "walking route")
    bike_route = _result_or_none(route_futures["cycling"], "cycling route")
    car_route = _result_or_none(route_futures["driving"], "driving route")
    weather = _result_or_none(weather_future, "weather")
    journey = _result_or_none(transit_future, "transit journey")

    crow_km = _haversine_km(
        trip.origin_lat, trip.origin_lon, trip.destination_lat, trip.destination_lon
    )
    car = _route_option(
        "car", car_route, crow_km, CAR_SPEED_KMH, CAR_COST_PLN_PER_KM, CAR_CO2_G_PER_KM
    )

    if journey is not None:
        transit = _journey_option(journey, depart_at)
    else:
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


def next_departure_utc(departure: clock_time | None, now_utc: datetime | None = None) -> datetime:
    """Next occurrence of a local (Gdańsk) wall-clock departure, as a UTC instant.

    zoneinfo applies the offset valid *on that day*, so DST changes are handled.
    Without a usual departure time, "now".
    """
    now_utc = now_utc or datetime.now(UTC)
    if departure is None:
        return now_utc
    local_now = now_utc.astimezone(LOCAL_TZ)
    target = datetime.combine(local_now.date(), departure, tzinfo=LOCAL_TZ)
    # Compare instants (UTC): comparing wall-clock times with one ZoneInfo ignores
    # `fold`, so in the repeated autumn hour a past time could look like the future.
    if target.astimezone(UTC) < now_utc:
        target = datetime.combine(local_now.date() + timedelta(days=1), departure, tzinfo=LOCAL_TZ)
    return target.astimezone(UTC)


def _journey_option(journey: TransitJourney, depart_at: datetime) -> ModeOption:
    rides = [leg for leg in journey.legs if leg.mode not in NON_RIDE_MODES]
    single_ztm_ride = len(rides) == 1 and rides[0].agency == ZTM_GDANSK_AGENCY
    if not rides:
        cost: float | None = 0.0  # walking-only "journey"
    elif single_ztm_ride:
        cost = TRANSIT_TICKET_PLN
    else:
        cost = None  # price varies by operator / ticket type
    co2 = sum(
        leg.distance_km * TRANSIT_CO2_G_PER_KM_BY_MODE.get(leg.mode, TRANSIT_CO2_G_PER_KM)
        for leg in rides
    )
    # Door to door from when you want to leave: includes waiting for the first
    # departure, so a tram at 04:30 isn't "25 min" when you asked for 23:30.
    arrival = datetime.fromisoformat(journey.end_time.replace("Z", "+00:00"))
    door_to_door_min = max(journey.duration_min, (arrival - depart_at).total_seconds() / 60)
    return ModeOption(
        mode="transit",
        duration_min=round(door_to_door_min, 1),
        distance_km=round(sum(leg.distance_km for leg in journey.legs), 2),
        cost_pln=cost,
        co2_g=round(co2),
        is_estimate=False,
        # One continuous line for the map; per-leg lines are in `legs`.
        geometry=[point for leg in journey.legs for point in leg.geometry],
        legs=journey.legs,
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
