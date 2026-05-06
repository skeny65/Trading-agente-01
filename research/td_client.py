"""
Twelve Data API client — fallback cuando Yahoo Finance está bloqueado.
Free tier: 800 calls/día, 8 credits/minuto.

Reglas:
- Solo se usa cuando yf_client está bloqueado (nunca como fuente primaria)
- Circuit breaker propio: rate limit → bloqueo por 65s (ventana 1-min de TD)
- Contador diario: si se agota el cupo, no llama más hasta el día siguiente
- reset() solo limpia el circuit breaker, no el contador diario
"""
import logging
import time
from datetime import date
from typing import Optional

import pandas as pd
import requests

import config

logger = logging.getLogger(__name__)

_BASE = "https://api.twelvedata.com"

# Símbolos que Twelve Data nombra diferente a yfinance
_YF_TO_TD: dict[str, str] = {
    "DX-Y.NYB": "DXY",       # índice dólar
    "BTC-USD":  "BTC/USD",   # bitcoin
    "^VIX":     "VIX",       # volatilidad
    "^VIX9D":   None,        # no disponible en free tier
    "^VIX3M":   None,        # no disponible en free tier
}

# --- estado del circuit breaker -----------------------------------------------
_blocked_until:  float = 0.0   # timestamp UNIX
_calls_today:    int   = 0
_calls_date:     str   = ""


def reset() -> None:
    """Nuevo ciclo → limpia bloqueo temporal (el contador diario persiste)."""
    global _blocked_until
    _blocked_until = 0.0


def is_blocked() -> bool:
    return time.time() < _blocked_until or _daily_exhausted()


def remaining_calls() -> int:
    _refresh_date()
    return max(0, config.TWELVE_DATA_DAILY_LIMIT - _calls_today)


# --- helpers internos ----------------------------------------------------------

def _refresh_date() -> None:
    global _calls_today, _calls_date
    today = date.today().isoformat()
    if _calls_date != today:
        _calls_today = 0
        _calls_date  = today


def _daily_exhausted() -> bool:
    _refresh_date()
    if _calls_today >= config.TWELVE_DATA_DAILY_LIMIT:
        logger.debug("[td_client] cupo diario agotado")
        return True
    return False


def _count(n: int = 1) -> None:
    _refresh_date()
    global _calls_today
    _calls_today += n


def _mark_blocked(seconds: int = 65) -> None:
    global _blocked_until
    _blocked_until = time.time() + seconds
    logger.warning(f"Twelve Data: rate limit — pausa {seconds}s")


def _map_symbol(yf_symbol: str) -> Optional[str]:
    """Convierte símbolo yfinance → símbolo Twelve Data. None = no soportado."""
    return _YF_TO_TD.get(yf_symbol, yf_symbol)


def _to_df(values: list[dict]) -> Optional[pd.DataFrame]:
    """Convierte lista de valores de TD a DataFrame compatible con yfinance."""
    if not values:
        return None
    df = pd.DataFrame(values)
    df.index = pd.to_datetime(df["datetime"])
    df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })
    cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[cols].astype(float)
    return df.sort_index()  # TD devuelve más-nuevo primero


def _get(endpoint: str, params: dict) -> Optional[dict]:
    """Petición GET a Twelve Data. Maneja errores y circuit breaker."""
    if not config.TWELVE_DATA_API_KEY:
        return None
    if is_blocked():
        logger.debug("[td_client] bloqueado — skip request")
        return None
    try:
        params["apikey"] = config.TWELVE_DATA_API_KEY
        r = requests.get(f"{_BASE}/{endpoint}", params=params, timeout=10)
        data = r.json()
        if isinstance(data, dict) and data.get("status") == "error":
            code = data.get("code", 0)
            msg  = data.get("message", "")
            if code in (429, 403) or "limit" in msg.lower():
                _mark_blocked()
            else:
                logger.warning(f"[td_client] API error {code}: {msg}")
            return None
        _count()
        return data
    except Exception as exc:
        logger.warning(f"[td_client] request error: {exc}")
        return None


# --- API pública ---------------------------------------------------------------

def safe_time_series(
    yf_symbol: str,
    interval: str = "1day",
    outputsize: int = 60,
) -> Optional[pd.DataFrame]:
    """
    Equivalente a yf.Ticker(symbol).history().
    yf_symbol: símbolo en formato yfinance (SPY, TLT, BTC-USD, etc.)
    interval: "1day" | "1h" | "4h" | "1week"
    outputsize: número de barras a retornar
    """
    td_sym = _map_symbol(yf_symbol)
    if td_sym is None:
        logger.debug(f"[td_client] {yf_symbol} no soportado en free tier")
        return None

    data = _get("time_series", {
        "symbol":     td_sym,
        "interval":   interval,
        "outputsize": outputsize,
        "order":      "ASC",
    })
    if data is None:
        return None
    df = _to_df(data.get("values", []))
    if df is not None:
        logger.info(f"[td_client] {yf_symbol}: {len(df)} barras ({interval}) — {remaining_calls()} calls restantes hoy")
    return df


def safe_batch_close(
    yf_symbols: list[str],
    interval: str = "1day",
    outputsize: int = 15,
) -> dict[str, Optional[pd.DataFrame]]:
    """
    Descarga varios símbolos de forma individual (TD free no tiene batch real).
    Retorna dict {yf_symbol: DataFrame | None}.
    Se detiene si el circuit breaker se activa a mitad del lote.
    """
    results: dict[str, Optional[pd.DataFrame]] = {}
    for sym in yf_symbols:
        if is_blocked():
            results[sym] = None
            continue
        results[sym] = safe_time_series(sym, interval=interval, outputsize=outputsize)
    return results
