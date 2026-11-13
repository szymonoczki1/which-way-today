import logging

import httpx
from pydantic import ValidationError

from app.clients.schemas import GeocodeResult

logger = logging.getLogger(__name__)

BASE_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy requires a descriptive User-Agent identifying the
# application; generic/browser-spoofing agents risk being rate-limited or blocked.
# TODO: replace the contact note with the public repo URL once it is pushed.
USER_AGENT = "which-way-today-mvp/1.0 (student recruitment project; contact via GitHub repo)"
TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# Nominatim's policy also asks clients to cache results. Only successes are cached,
# so a transient outage doesn't permanently turn an address into "not found".
_cache: dict[str, GeocodeResult] = {}


def geocode(address: str) -> GeocodeResult | None:
    key = address.strip().lower()
    if key in _cache:
        return _cache[key]

    try:
        response = httpx.get(
            BASE_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        results = response.json()
        if not results:
            return None
        first = results[0]
        result = GeocodeResult(
            lat=float(first["lat"]),
            lon=float(first["lon"]),
            display_name=first["display_name"],
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, ValidationError):
        # ValueError also covers json.JSONDecodeError (e.g. an HTML rate-limit page).
        logger.warning("Nominatim geocode failed for %r", address, exc_info=True)
        return None

    _cache[key] = result
    return result
