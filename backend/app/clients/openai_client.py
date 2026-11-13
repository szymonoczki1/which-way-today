"""Minimal OpenAI Chat Completions client (plain httpx, no SDK).

Optional by design: without a key it returns None immediately, and any failure
(timeout, HTTP error, quota, malformed reply) also returns None, so callers
always have a deterministic fallback.
"""

import json
import logging

import httpx

logger = logging.getLogger(__name__)

URL = "https://api.openai.com/v1/chat/completions"
# Keeps the recommendation endpoint responsive; the rule-based answer is used if
# the model is slower than this. (Per-operation limits, so roughly 8 s worst case.)
TIMEOUT = httpx.Timeout(6.0, connect=2.0)


def complete_json(
    system: str, user: str, *, api_key: str | None, model: str
) -> dict[str, object] | None:
    """Ask the model for a JSON object. Returns None if unavailable or invalid."""
    # Docker passes an unset OPENAI_API_KEY as "", so test emptiness, not None.
    if not api_key or not api_key.strip():
        return None
    try:
        response = httpx.post(
            URL,
            headers={"Authorization": f"Bearer {api_key.strip()}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        # Type name only: exception messages could echo request details.
        logger.warning("OpenAI completion failed (%s); using fallback", type(exc).__name__)
        return None
    if not isinstance(parsed, dict):
        logger.warning("OpenAI returned non-object JSON; using fallback")
        return None
    return parsed
