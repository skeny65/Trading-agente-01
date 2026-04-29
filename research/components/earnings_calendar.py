"""
Detecta si hay earnings de los top 10 holdings de SPY en las próximas 48h.
Si hay ≥3, activa veto de entrada (riesgo de gap inesperado).
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import yfinance as yf

import config
from research.components.top_holdings import SPY_TOP_10

logger = logging.getLogger(__name__)


@dataclass
class EarningsAlert:
    symbol: str
    company: str
    weight: float
    earnings_date: str        # YYYY-MM-DD
    hours_away: float
    timing: str               # "BMO" (before market open) | "AMC" (after close) | "TBD"


@dataclass
class EarningsData:
    alerts: list[EarningsAlert]   # earnings en las próximas 48h
    count_upcoming: int
    veto_active: bool             # True si count >= EARNINGS_TOP10_THRESHOLD
    heaviest_name: str | None     # nombre de la empresa con mayor peso en SPY


def _get_earnings_date(symbol: str) -> str | None:
    try:
        ticker   = yf.Ticker(symbol)
        cal      = ticker.calendar
        if cal is None or cal.empty:
            return None
        # yfinance retorna un DataFrame con 'Earnings Date' como columna
        if "Earnings Date" in cal.columns:
            date = cal["Earnings Date"].iloc[0]
        elif "Earnings Date" in cal.index:
            date = cal.loc["Earnings Date"].iloc[0]
        else:
            return None
        return str(date)[:10] if date else None
    except Exception:
        return None


def get_earnings_data(hours_ahead: int = 48) -> EarningsData:
    now     = datetime.now(timezone.utc)
    cutoff  = now + timedelta(hours=hours_ahead)
    alerts: list[EarningsAlert] = []

    for holding in SPY_TOP_10:
        sym    = holding["symbol"]
        date_s = _get_earnings_date(sym)
        if not date_s:
            continue
        try:
            date_dt    = datetime.strptime(date_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            hours_away = (date_dt - now).total_seconds() / 3600
            if 0 <= hours_away <= hours_ahead:
                alerts.append(EarningsAlert(
                    symbol=sym,
                    company=holding["name"],
                    weight=holding["weight"],
                    earnings_date=date_s,
                    hours_away=round(hours_away, 1),
                    timing="TBD",
                ))
        except Exception:
            pass

    alerts.sort(key=lambda a: a.hours_away)
    veto_active = len(alerts) >= config.EARNINGS_TOP10_THRESHOLD
    heaviest = max(alerts, key=lambda a: a.weight).company if alerts else None

    if alerts:
        names = ", ".join(f"{a.company} ({a.hours_away:.0f}h)" for a in alerts)
        logger.warning(
            f"Earnings próximos en top 10 SPY: {names} "
            f"| veto={'SÍ' if veto_active else 'NO'}"
        )
    else:
        logger.info("Sin earnings de top 10 SPY en próximas 48h")

    return EarningsData(
        alerts=alerts,
        count_upcoming=len(alerts),
        veto_active=veto_active,
        heaviest_name=heaviest,
    )
