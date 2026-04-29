"""
Calendario económico: detecta eventos de alto impacto en las próximas 48h.
Fuente: Trading Economics (scraping) + hardcoded mensual para CPI/NFP/PCE.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests

logger = logging.getLogger(__name__)

_TE_URL  = "https://tradingeconomics.com/calendar"
_TIMEOUT = 10

# Patrones de eventos de alto impacto a detectar (case-insensitive)
_EXTREME_PATTERNS = [
    r"fomc",
    r"federal open market",
    r"interest rate decision",
    r"fed rate",
    r"cpi",
    r"consumer price index",
    r"non.?farm payroll",
    r"nfp",
    r"unemployment rate",
]

_HIGH_PATTERNS = [
    r"core pce",
    r"personal consumption",
    r"gdp",
    r"gross domestic product",
    r"ism manufacturing",
    r"ism services",
    r"retail sales",
    r"powell",
    r"fed chair",
    r"fomc minutes",
    r"triple witching",
]


@dataclass
class EconomicEvent:
    date: str           # YYYY-MM-DD
    time_et: str        # HH:MM o "TBD"
    event: str
    impact: str         # "EXTREMO" | "ALTO" | "MEDIO"
    hours_away: float   # horas desde ahora


def _classify_event(title: str) -> str | None:
    title_lower = title.lower()
    for pattern in _EXTREME_PATTERNS:
        if re.search(pattern, title_lower):
            return "EXTREMO"
    for pattern in _HIGH_PATTERNS:
        if re.search(pattern, title_lower):
            return "ALTO"
    return None


def _parse_te_events(html: str, now: datetime) -> list[EconomicEvent]:
    events = []
    # Busca celdas con datos de calendario en Trading Economics
    pattern = r'<td[^>]*data-date="([^"]+)"[^>]*>.*?<td[^>]*>(.*?)</td>'
    for m in re.finditer(pattern, html, re.DOTALL):
        date_str = m.group(1)[:10]
        title    = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        impact   = _classify_event(title)
        if not impact:
            continue
        try:
            event_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            hours_away = (event_dt - now).total_seconds() / 3600
            if -2 <= hours_away <= 72:
                events.append(EconomicEvent(
                    date=date_str, time_et="08:30",
                    event=title, impact=impact, hours_away=hours_away,
                ))
        except ValueError:
            pass
    return events


def get_upcoming_high_impact_events(hours_ahead: int = 48) -> list[EconomicEvent]:
    """
    Retorna eventos de impacto EXTREMO o ALTO en las próximas `hours_ahead` horas.
    Si el scraping falla, retorna lista vacía (el agente opera con cautela normal).
    """
    now = datetime.now(timezone.utc)
    events: list[EconomicEvent] = []

    try:
        resp = requests.get(
            _TE_URL,
            timeout=_TIMEOUT,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        resp.raise_for_status()
        events = _parse_te_events(resp.text, now)
    except Exception as exc:
        logger.debug(f"Trading Economics calendar no disponible: {exc}")

    # Filtrar por ventana de tiempo
    relevant = [e for e in events if 0 <= e.hours_away <= hours_ahead]
    if relevant:
        for e in relevant:
            logger.warning(
                f"Evento {e.impact}: '{e.event}' en {e.hours_away:.1f}h ({e.date})"
            )
    else:
        logger.info(f"Sin eventos de alto impacto en próximas {hours_ahead}h")

    return relevant


def get_defensive_mode(events: list[EconomicEvent]) -> dict:
    """
    Evalúa si el agente debe entrar en modo defensivo basado en eventos próximos.
    Retorna: {
      "veto": bool,          — True = no abrir nuevas posiciones
      "score_multiplier": float,  — 1.0 normal / 0.5 reducido / 0.0 veto total
      "reason": str,
    }
    """
    if not events:
        return {"veto": False, "score_multiplier": 1.0, "reason": "sin_eventos"}

    extreme = [e for e in events if e.impact == "EXTREMO"]
    high    = [e for e in events if e.impact == "ALTO"]

    # Evento extremo en < 12h → veto total
    if any(e.hours_away < 12 for e in extreme):
        evt = next(e for e in extreme if e.hours_away < 12)
        return {
            "veto":             True,
            "score_multiplier": 0.0,
            "reason":           f"VETO: {evt.event} en {evt.hours_away:.1f}h",
        }

    # Evento extremo en < 24h → score reducido a 0.5
    if extreme:
        evt = extreme[0]
        return {
            "veto":             False,
            "score_multiplier": 0.50,
            "reason":           f"CAUTELA: {evt.event} en {evt.hours_away:.1f}h",
        }

    # Evento alto en < 24h → score reducido a 0.85
    if any(e.hours_away < 24 for e in high):
        evt = next(e for e in high if e.hours_away < 24)
        return {
            "veto":             False,
            "score_multiplier": 0.85,
            "reason":           f"PRECAUCION: {evt.event} en {evt.hours_away:.1f}h",
        }

    return {"veto": False, "score_multiplier": 1.0, "reason": "sin_eventos_criticos"}
