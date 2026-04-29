"""
Cliente HTTP para FRED API (Federal Reserve Bank of St. Louis).
Obtiene series económicas con caché local de 4 horas para no exceder límites.
"""
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)

_CACHE_DIR  = Path(__file__).parent.parent.parent / "state" / "fred_cache"
_CACHE_TTL  = 4 * 3600  # 4 horas
_BASE_URL   = "https://api.stlouisfed.org/fred/series/observations"
_TIMEOUT    = 10


def _cache_path(series_id: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{series_id}.json"


def _load_cache(series_id: str) -> dict | None:
    path = _cache_path(series_id)
    try:
        data = json.loads(path.read_text())
        age  = time.time() - data.get("cached_at", 0)
        if age < _CACHE_TTL:
            return data
    except Exception:
        pass
    return None


def _save_cache(series_id: str, payload: dict) -> None:
    try:
        payload["cached_at"] = time.time()
        _cache_path(series_id).write_text(json.dumps(payload))
    except Exception:
        pass


def get_series(series_id: str, limit: int = 5) -> list[dict]:
    """
    Retorna las últimas `limit` observaciones de una serie FRED.
    Cada item: {"date": "YYYY-MM-DD", "value": float | None}
    Retorna [] si la API falla (el agente usa fallback neutral).
    """
    cached = _load_cache(series_id)
    if cached:
        return cached.get("observations", [])

    try:
        resp = requests.get(
            _BASE_URL,
            params={
                "series_id":       series_id,
                "api_key":         config.FRED_API_KEY,
                "file_type":       "json",
                "sort_order":      "desc",
                "limit":           limit,
                "observation_end": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json().get("observations", [])
        observations = []
        for obs in raw:
            val = obs.get("value", ".")
            observations.append({
                "date":  obs["date"],
                "value": None if val == "." else float(val),
            })
        _save_cache(series_id, {"observations": observations})
        logger.debug(f"FRED {series_id}: {len(observations)} observaciones")
        return observations
    except Exception as exc:
        logger.warning(f"FRED {series_id} error: {exc}")
        return []


def get_latest_value(series_id: str) -> float | None:
    """Retorna el último valor no-nulo de la serie."""
    observations = get_series(series_id, limit=10)
    for obs in observations:
        if obs["value"] is not None:
            return obs["value"]
    return None
