import logging
from dataclasses import dataclass

from analysis.sentiment_analyzer import SentimentResult
from research.macro_indicators import MacroContext
from research.market_data import Quote

logger = logging.getLogger(__name__)

# Pesos del score compuesto (deben sumar 1.0)
_W_SENTIMENT = 0.30
_W_TREND     = 0.30
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
    # compound va de -1 a +1 → normalizamos a 0–1
    return round((s.compound + 1) / 2, 3)


def _score_trend(q: Quote) -> float:
    # bullish=1.0, neutral=0.5, bearish=0.0
    # + bonus por volume_ratio alto (momentum de volumen)
    base = {"bullish": 1.0, "neutral": 0.5, "bearish": 0.0}[q.trend]
    # volumen mayor al doble del promedio suma hasta 0.1 extra
    vol_bonus = min((q.volume_ratio - 1.0) * 0.1, 0.1) if q.volume_ratio > 1.0 else 0.0
    return round(min(base + vol_bonus, 1.0), 3)


def _score_macro(ctx: MacroContext) -> float:
    # Fear & Greed normalizado a 0–1
    return round(ctx.fear_greed_score / 100, 3)


def _score_vix(ctx: MacroContext) -> float:
    # VIX bajo → score alto (mercado calmado = favorable para operar)
    mapping = {"low": 1.0, "moderate": 0.65, "high": 0.30, "extreme": 0.0}
    return mapping.get(ctx.vix_regime, 0.5)


def calculate(
    quote: Quote,
    sentiment: SentimentResult,
    macro: MacroContext,
) -> ScoreBreakdown:
    s_sentiment = _score_sentiment(sentiment)
    s_trend     = _score_trend(quote)
    s_macro     = _score_macro(macro)
    s_vix       = _score_vix(macro)

    total = (
        s_sentiment * _W_SENTIMENT
        + s_trend   * _W_TREND
        + s_macro   * _W_MACRO
        + s_vix     * _W_VIX
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
        f"| sentiment={s_sentiment:.2f} trend={s_trend:.2f} "
        f"macro={s_macro:.2f} vix={s_vix:.2f}"
    )
    return breakdown
