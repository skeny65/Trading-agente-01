"""
Fechas oficiales de reuniones FOMC desde la Fed.
Cache local diario en state/upcoming_events.json.
"""
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_FOMC_URL   = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
_STATE_FILE = Path(__file__).parent.parent.parent / "state" / "upcoming_events.json"
_CACHE_TTL  = 24 * 3600  # 1 día
_TIMEOUT    = 10


def _load_state() -> dict:
    try:
        return json.loads(_STATE_FILE.read_text())
    except Exception:
        return {"last_updated": None, "events": []}


def _save_state(data: dict) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _STATE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as exc:
        logger.warning(f"No se pudo guardar state: {exc}")


def _parse_fomc_dates(html: str) -> list[str]:
    """Extrae fechas de reuniones FOMC del HTML de la Fed."""
    # Busca patrones como "January 28-29, 2026" o "March 18-19, 2026"
    month_map = {
        "January":1,"February":2,"March":3,"April":4,"May":5,"June":6,
        "July":7,"August":8,"September":9,"October":10,"November":11,"December":12,
    }
    pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d+)(?:-\d+)?,\s+(\d{4})"
    dates = []
    for m in re.finditer(pattern, html):
        month_name, day, year = m.group(1), int(m.group(2)), int(m.group(3))
        month = month_map[month_name]
        try:
            date_str = f"{year}-{month:02d}-{day:02d}"
            dates.append(date_str)
        except ValueError:
            pass
    return sorted(set(dates))


def _fetch_fomc_dates() -> list[str]:
    try:
        resp = requests.get(_FOMC_URL, timeout=_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        dates = _parse_fomc_dates(resp.text)
        logger.info(f"FOMC: {len(dates)} reuniones parseadas")
        return dates
    except Exception as exc:
        logger.warning(f"FOMC calendar error: {exc}")
        return []


def get_fomc_events() -> list[dict]:
    """
    Retorna lista de eventos FOMC como:
    [{"date": "2026-05-07", "event": "FOMC Meeting", "impact": "EXTREMO", "source": "fed_calendar"}]
    Usa caché de 24h.
    """
    state = _load_state()
    last_updated = state.get("last_updated")
    cached_events = [e for e in state.get("events", []) if e.get("source") == "fed_calendar"]

    needs_refresh = True
    if last_updated:
        age = time.time() - last_updated
        if age < _CACHE_TTL and cached_events:
            needs_refresh = False

    if needs_refresh:
        dates = _fetch_fomc_dates()
        fomc_events = [
            {
                "date":        d,
                "time_et":     "14:00",
                "event":       "FOMC Meeting",
                "impact":      "EXTREMO",
                "source":      "fed_calendar",
                "affects_spy": True,
            }
            for d in dates
        ]
        # Preservar eventos de otras fuentes, reemplazar solo fed_calendar
        other_events = [e for e in state.get("events", []) if e.get("source") != "fed_calendar"]
        state["events"]       = other_events + fomc_events
        state["last_updated"] = time.time()
        _save_state(state)
        return fomc_events

    return cached_events
