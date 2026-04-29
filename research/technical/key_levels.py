"""
Detección de niveles clave de precio: máximos/mínimos históricos, soportes y resistencias.
"""
import logging
from dataclasses import dataclass

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class KeyLevels:
    high_20d: float | None
    low_20d: float | None
    high_50d: float | None
    low_50d: float | None
    high_52w: float | None
    low_52w: float | None
    prev_close: float | None
    distance_to_52w_high: float | None  # % desde precio actual
    distance_to_52w_low: float | None   # %


def get_key_levels(df: pd.DataFrame) -> KeyLevels:
    """
    Calcula niveles clave desde historial diario.
    Requiere al menos 252 filas para 52w.
    """
    close = df["Close"]
    n     = len(close)

    def _high(window: int) -> float | None:
        w = min(window, n)
        return float(close.iloc[-w:].max()) if w > 0 else None

    def _low(window: int) -> float | None:
        w = min(window, n)
        return float(close.iloc[-w:].min()) if w > 0 else None

    current = float(close.iloc[-1]) if n > 0 else None
    h52w    = _high(252)
    l52w    = _low(252)

    dist_high = round((current - h52w) / h52w * 100, 2) if current and h52w else None
    dist_low  = round((current - l52w) / l52w * 100, 2) if current and l52w else None

    levels = KeyLevels(
        high_20d=_high(20),
        low_20d=_low(20),
        high_50d=_high(50),
        low_50d=_low(50),
        high_52w=h52w,
        low_52w=l52w,
        prev_close=float(close.iloc[-2]) if n >= 2 else None,
        distance_to_52w_high=dist_high,
        distance_to_52w_low=dist_low,
    )
    logger.debug(
        f"Niveles: 52w_high={h52w:.2f} ({dist_high:+.1f}%) | "
        f"52w_low={l52w:.2f} ({dist_low:+.1f}%)"
        if h52w and l52w else "Niveles: datos insuficientes"
    )
    return levels
