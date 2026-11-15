import logging
import threading
import time

import httpx
from pydantic import ValidationError

from app.clients.schemas import GeocodeResult

logger = logging.getLogger(__name__)

BASE_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent identifying the
# application; generic/browser-spoofing agents risk being rate-limited or blocked.
USER_AGENT = "which-way-today/1.0 (+https://github.com/szymonoczki1/which-way-today)"
# Per-operation limits (connect, then each read), not a total cap: a server that
# trickles bytes can exceed 8 s. Accepted for the MVP; see comparison_service for
# how the comparison endpoint bounds its overall time.
TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# Nominatim policy: at most 1 request/s per application. Calls are serialized
# process-wide, so a burst queues up instead of getting the server IP blocked.
MIN_INTERVAL_S = 1.0
_throttle_lock = threading.Lock()
_last_request_at = 0.0

# Nominatim's policy also asks clients to cache results. Only successes are cached,
# so a transient outage doesn't permanently turn an address into "not found".
# Bounded because /geocode takes arbitrary user input; oldest entries are evicted.
CACHE_MAX_ENTRIES = 1000
_cache: dict[str, GeocodeResult] = {}


class GeocodingUnavailableError(Exception):
    """Nominatim could not answer (timeout, 4xx/5xx, rate limit, malformed body).

    Kept distinct from a None return ("no such address") so the API can answer
    503 instead of wrongly telling the user their address does not exist."""


def geocode(address: str) -> GeocodeResult | None:
    """Return the best match, or None if Nominatim found nothing.

    Raises GeocodingUnavailableError if Nominatim itself failed."""
    key = address.strip().lower()
    if key in _cache:
        return _cache[key]

    _wait_for_rate_limit_slot()
    try:
        response = httpx.get(
            BASE_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()
        if not isinstance(results, list):
            raise TypeError(f"expected a JSON list, got {type(results).__name__}")
        if not results:
            return None
        first = results[0]
        result = GeocodeResult(
            lat=float(first["lat"]),
            lon=float(first["lon"]),
            display_name=first["display_name"],
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, ValidationError) as exc:
        # ValueError also covers json.JSONDecodeError (e.g. an HTML rate-limit page).
        logger.warning("Nominatim geocode failed for %r", address, exc_info=True)
        raise GeocodingUnavailableError(f"Geocoding failed for {address!r}") from exc

    if len(_cache) >= CACHE_MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))  # dicts keep insertion order -> oldest first
    _cache[key] = result
    return result


def _wait_for_rate_limit_slot() -> None:
    global _last_request_at
    with _throttle_lock:
        wait_s = _last_request_at + MIN_INTERVAL_S - time.monotonic()
        if wait_s > 0:
            time.sleep(wait_s)
        _last_request_at = time.monotonic()
