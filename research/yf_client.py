"""
Circuit breaker para Yahoo Finance.
Primer error de rate-limit en un ciclo → bloquea Yahoo para ese ciclo completo.
Todas las llamadas siguientes retornan None al instante — sin esperas, sin reintentos.
Al inicio del siguiente ciclo se llama reset() y se vuelve a intentar.
"""
import logging
import time
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

_RATE_LIMIT_KEYWORDS = ("too many requests", "rate limit", "429", "ratelimit")

# Timestamp hasta el que Yahoo está bloqueado (0 = no bloqueado)
_blocked_until: float = 0.0


def reset() -> None:
    """Llamar al inicio de cada ciclo para dar a Yahoo una nueva oportunidad."""
    global _blocked_until
    _blocked_until = 0.0


def is_blocked() -> bool:
    return time.time() < _blocked_until


def _mark_blocked() -> None:
    global _blocked_until
    # Bloquear hasta 5 minutos antes del próximo ciclo (55 min)
    _blocked_until = time.time() + 55 * 60
    logger.warning(
        "Yahoo Finance: rate limit detectado — "
        "skipping todas las llamadas de este ciclo, se reintenta en el proximo"
    )


def _is_rate_limit(exc: Exception) -> bool:
    return any(k in str(exc).lower() for k in _RATE_LIMIT_KEYWORDS)


def safe_history(symbol: str, **kwargs) -> Optional[pd.DataFrame]:
    """
    yf.Ticker(symbol).history(**kwargs) con circuit breaker.
    Retorna None si Yahoo está bloqueado o si falla.
    """
    if is_blocked():
        logger.debug(f"[yf_client] bloqueado — skip {symbol}")
        return None
    try:
        df = yf.Ticker(symbol).history(**kwargs)
        return df if (df is not None and not df.empty) else None
    except Exception as exc:
        if _is_rate_limit(exc):
            _mark_blocked()
        else:
            logger.warning(f"[yf_client] {symbol}: {exc}")
        return None


def safe_download(symbols, **kwargs) -> Optional[pd.DataFrame]:
    """
    yf.download(symbols, **kwargs) con circuit breaker.
    Retorna None si Yahoo está bloqueado o si falla.
    """
    if is_blocked():
        logger.debug(f"[yf_client] bloqueado — skip download {symbols}")
        return None
    try:
        df = yf.download(symbols, **kwargs)
        return df if (df is not None and not df.empty) else None
    except Exception as exc:
        if _is_rate_limit(exc):
            _mark_blocked()
        else:
            logger.warning(f"[yf_client] download {symbols}: {exc}")
        return None
