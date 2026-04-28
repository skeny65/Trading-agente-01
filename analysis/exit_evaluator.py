"""
Evalúa si una posición abierta debe cerrarse por invalidación de tesis.

Cuatro triggers independientes — basta con que uno se cumpla:
  1. VIX spike extremo (VIX > 30)
  2. Reversión de tendencia con volumen anómalo (price < SMA20 + vol_ratio > 1.5)
  3. Crash de sentimiento (compound < -0.5 con >= 5 titulares)
  4. Tiempo máximo de holding alcanzado
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import config
from analysis.sentiment_analyzer import SentimentResult
from research.macro_indicators import MacroContext
from research.market_data import Quote

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    should_close: bool
    reason: str       # vacío si should_close=False


def evaluate_exit(
    symbol: str,
    quote: Quote,
    sentiment: SentimentResult,
    macro: MacroContext,
    position: dict,
) -> ExitSignal:
    """
    position dict (de open_positions.json):
      opened_at           str   ISO timestamp UTC
      vix_regime_at_entry str   régimen VIX al abrir
      max_holding_days    int   días máximos según régimen
    """

    # Trigger 1 — VIX spike extremo
    if macro.vix_regime == "extreme":
        logger.warning(f"[EXIT] {symbol}: VIX extremo ({macro.vix:.1f}) — cerrando")
        return ExitSignal(
            should_close=True,
            reason=f"vix_spike_extreme: VIX={macro.vix:.1f}",
        )

    # Trigger 2 — Reversión de tendencia con volumen
    if quote.trend == "bearish" and quote.volume_ratio > 1.5:
        logger.warning(
            f"[EXIT] {symbol}: reversion tendencia con volumen "
            f"(price_vs_sma20={quote.price_vs_sma20:.1f}%, vol_ratio={quote.volume_ratio:.2f}x)"
        )
        return ExitSignal(
            should_close=True,
            reason=(
                f"trend_reversal_with_volume: "
                f"price_vs_sma20={quote.price_vs_sma20:.1f}% vol_ratio={quote.volume_ratio:.2f}x"
            ),
        )

    # Trigger 3 — Crash de sentimiento
    if sentiment.compound < -0.5 and sentiment.headline_count >= 5:
        logger.warning(
            f"[EXIT] {symbol}: crash sentimiento "
            f"(compound={sentiment.compound:.2f}, {sentiment.headline_count} titulares)"
        )
        return ExitSignal(
            should_close=True,
            reason=(
                f"sentiment_crash: compound={sentiment.compound:.2f} "
                f"headlines={sentiment.headline_count}"
            ),
        )

    # Trigger 4 — Tiempo máximo de holding
    opened_at_str = position.get("opened_at", "")
    max_days      = position.get("max_holding_days", config.MAX_HOLDING_DAYS_MODERATE)
    if opened_at_str:
        try:
            opened_at = datetime.fromisoformat(opened_at_str)
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            elapsed_days = (datetime.now(timezone.utc) - opened_at).days
            if elapsed_days >= max_days:
                logger.warning(
                    f"[EXIT] {symbol}: holding maximo alcanzado "
                    f"({elapsed_days}d >= {max_days}d)"
                )
                return ExitSignal(
                    should_close=True,
                    reason=f"max_holding_reached: {elapsed_days}d >= {max_days}d",
                )
        except Exception:
            pass

    return ExitSignal(should_close=False, reason="")
