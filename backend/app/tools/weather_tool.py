"""
Historical weather lookup via the Open-Meteo archive API (free, no API key needed).
https://open-meteo.com/en/docs/historical-weather-api

- Results are cached in backend/data/weather_cache.json, keyed by coordinates + date range,
  so repeated runs never re-hit the API for the same lookup.
- This function never raises. If the lookup can't be done (dates out of range, network
  error, API error), it returns {"status": "unavailable", "reason": "..."} instead of
  crashing or inventing data. Failures are not cached, so a later run can retry.
"""

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "weather_cache.json"
DAILY_VARIABLES = "temperature_2m_min,temperature_2m_max,precipitation_sum,snowfall_sum"

EARLIEST_ARCHIVE_DATE = date(1940, 1, 1)
# The archive lags behind real time by a few days, so very recent dates have no data yet.
ARCHIVE_DELAY_DAYS = 5


def get_historical_weather(latitude, longitude, start_date, end_date):
    """Daily weather for a location and date range (dates are datetime.date objects).

    Returns on success:
        {"status": "ok", "from_cache": bool, "request_url": str, "fetched_at": str,
         "response": <raw Open-Meteo JSON>}
    Returns on failure:
        {"status": "unavailable", "reason": str}
    """
    latest_available = date.today() - timedelta(days=ARCHIVE_DELAY_DAYS)
    if start_date < EARLIEST_ARCHIVE_DATE or end_date > latest_available:
        return _unavailable(
            f"dates {start_date} to {end_date} are outside the archive range "
            f"({EARLIEST_ARCHIVE_DATE} to {latest_available})"
        )

    cache_key = f"{latitude:.4f},{longitude:.4f},{start_date},{end_date}"
    cache = _load_cache()
    if cache_key in cache:
        return {"status": "ok", "from_cache": True, **cache[cache_key]}

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "daily": DAILY_VARIABLES,
        "timezone": "auto",  # daily values use the location's local days
    }
    try:
        response = httpx.get(ARCHIVE_URL, params=params, timeout=15)
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:  # network failure or non-JSON reply
        return _unavailable(f"request failed ({error.__class__.__name__}: {error})")

    if response.status_code != 200 or data.get("error"):
        return _unavailable(f"API returned HTTP {response.status_code}: {data.get('reason', 'no reason given')}")

    entry = {
        "request_url": str(response.url),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "response": data,
    }
    cache[cache_key] = entry
    _save_cache(cache)
    return {"status": "ok", "from_cache": False, **entry}


def _unavailable(reason):
    return {"status": "unavailable", "reason": reason}


def _load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
