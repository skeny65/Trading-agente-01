import logging
from dataclasses import dataclass

from analysis.sentiment_analyzer import SentimentResult
from research.macro_indicators import MacroContext
from research.market_data import Quote

logger = logging.getLogger(__name__)

# Pesos del score compuesto — estrategia swing (deben sumar 1.0)
# La tendencia pesa más porque en swing trading la dirección de precio es dominante
_W_TREND     = 0.40
_W_SENTIMENT = 0.20
_W_MACRO     = 0.25
_W_VIX       = 0.15


@dataclass
class ScoreBreakdown:
    sentiment: float
    trend: float
    macro: float
    vix: float
    total: float


def _score_sentiment(s: SentimentResult) -> float:
    return round((s.compound + 1) / 2, 3)


def _score_trend(q: Quote) -> float:
    # Usa trend_strength (cruces SMA20/SMA50) para mayor precisión en swing
    strength_map = {
        "strong_bullish": 1.0,
        "bullish":        0.75,
        "neutral":        0.50,
        "bearish":        0.25,
        "strong_bearish": 0.0,
    }
    base = strength_map.get(q.trend_strength, 0.50)
    # Bonus de volumen: confirma el movimiento (hasta +0.1 extra)
    vol_bonus = min((q.volume_ratio - 1.0) * 0.1, 0.1) if q.volume_ratio > 1.0 else 0.0
    return round(min(base + vol_bonus, 1.0), 3)


def _score_macro(ctx: MacroContext) -> float:
    return round(ctx.fear_greed_score / 100, 3)


def _score_vix(ctx: MacroContext) -> float:
    mapping = {"low": 1.0, "moderate": 0.65, "high": 0.30, "extreme": 0.0}
    return mapping.get(ctx.vix_regime, 0.5)


def calculate(
    quote: Quote,
    sentiment: SentimentResult,
    macro: MacroContext,
) -> ScoreBreakdown:
    s_trend     = _score_trend(quote)
    s_sentiment = _score_sentiment(sentiment)
    s_macro     = _score_macro(macro)
    s_vix       = _score_vix(macro)

    total = (
        s_trend     * _W_TREND
        + s_sentiment * _W_SENTIMENT
        + s_macro     * _W_MACRO
        + s_vix       * _W_VIX
    )

    breakdown = ScoreBreakdown(
        sentiment=s_sentiment,
        trend=s_trend,
        macro=s_macro,
        vix=s_vix,
        total=round(total, 3),
    )

    logger.info(
        f"Score [{quote.symbol}]: total={total:.3f} "
        f"| trend={s_trend:.2f}({quote.trend_strength}) "
        f"sentiment={s_sentiment:.2f} macro={s_macro:.2f} vix={s_vix:.2f}"
    )
    return breakdown
