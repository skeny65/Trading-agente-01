import logging
from dataclasses import dataclass
from enum import Enum

import config
from analysis.opportunity_scorer import ScoreBreakdown
from analysis.sentiment_analyzer import SentimentResult
from research.macro_indicators import MacroContext
from research.market_data import Quote

logger = logging.getLogger(__name__)


class Decision(str, Enum):
    APPROVE   = "APPROVE"
    REJECT    = "REJECT"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass
class EvaluationResult:
    decision:   Decision
    action:     str           # "buy" | "close" | "none"
    confidence: float
    size:       float
    reason:     str
    symbol:     str
    score:      ScoreBreakdown


def evaluate(
    symbol: str,
    quote: Quote,
    sentiment: SentimentResult,
    macro: MacroContext,
    score: ScoreBreakdown,
) -> EvaluationResult:

    # ── Regla 0: bloqueo por VIX extremo ────────────────────────────────────
    if config.BLOCK_NEW_ON_EXTREME_VIX and macro.vix_regime == "extreme":
        return EvaluationResult(
            decision=Decision.NO_SIGNAL,
            action="none",
            confidence=score.total,
            size=0.0,
            reason=f"VIX extremo ({macro.vix:.1f}) — no se abren nuevas posiciones",
            symbol=symbol,
            score=score,
        )

    # ── Regla 1: score mínimo ────────────────────────────────────────────────
    if score.total < config.MIN_CONFIDENCE:
        return EvaluationResult(
            decision=Decision.NO_SIGNAL,
            action="none",
            confidence=score.total,
            size=0.0,
            reason=f"Score {score.total:.3f} < umbral {config.MIN_CONFIDENCE}",
            symbol=symbol,
            score=score,
        )

    # ── Regla 2: consenso de señales (configurable, default 3/3) ────────────
    bullish_signals = sum([
        quote.trend == "bullish",
        sentiment.label == "positive",
        macro.macro_bias == "bullish",
    ])
    bearish_signals = sum([
        quote.trend == "bearish",
        sentiment.label == "negative",
        macro.macro_bias == "bearish",
    ])

    required = config.CONSENSUS_REQUIRED

    if bullish_signals >= required:
        action = "buy"
        reason = (
            f"Score {score.total:.3f} | {bullish_signals}/3 senales alcistas "
            f"| trend={quote.trend_strength} sentiment={sentiment.label} macro={macro.macro_bias}"
        )
    elif bearish_signals >= 2:
        return EvaluationResult(
            decision=Decision.NO_SIGNAL,
            action="none",
            confidence=score.total,
            size=0.0,
            reason=f"Senal bajista ({bearish_signals}/3) — sin operacion larga",
            symbol=symbol,
            score=score,
        )
    else:
        return EvaluationResult(
            decision=Decision.NO_SIGNAL,
            action="none",
            confidence=score.total,
            size=0.0,
            reason=f"Consenso insuficiente ({bullish_signals}/{required} bullish requeridas)",
            symbol=symbol,
            score=score,
        )

    # ── Tamaño dinámico (sizing conservador para swing) ──────────────────────
    # score >= 0.85 → 8% | >= 0.78 → 5% | >= 0.70 → 3%
    if score.total >= 0.85:
        size = config.SIZE_HIGH_CONFIDENCE
    elif score.total >= 0.78:
        size = config.SIZE_MEDIUM_CONFIDENCE
    else:
        size = config.SIZE_LOW_CONFIDENCE

    logger.info(
        f"APPROVE [{symbol}]: {action.upper()} | confidence={score.total:.3f} "
        f"| size={size} | trend_strength={quote.trend_strength}"
    )

    return EvaluationResult(
        decision=Decision.APPROVE,
        action=action,
        confidence=score.total,
        size=size,
        reason=reason,
        symbol=symbol,
        score=score,
    )
