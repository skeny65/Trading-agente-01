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
    APPROVE  = "APPROVE"
    REJECT   = "REJECT"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass
class EvaluationResult:
    decision: Decision
    action: str          # "buy" | "sell" | "none"
    confidence: float
    size: float
    reason: str
    symbol: str
    score: ScoreBreakdown


def evaluate(
    symbol: str,
    quote: Quote,
    sentiment: SentimentResult,
    macro: MacroContext,
    score: ScoreBreakdown,
) -> EvaluationResult:

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

    # ── Regla 2: consenso de señales ────────────────────────────────────────
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

    # Necesitamos al menos 2 de 3 señales alineadas
    if bullish_signals >= 2:
        action = "buy"
        reason = (
            f"Score {score.total:.3f} | {bullish_signals}/3 señales alcistas "
            f"| trend={quote.trend} sentiment={sentiment.label} macro={macro.macro_bias}"
        )
    elif bearish_signals >= 2:
        # Por ahora agente01 solo opera en largo (SPY/QQQ).
        # Señal bajista = no operar (no hay short).
        return EvaluationResult(
            decision=Decision.NO_SIGNAL,
            action="none",
            confidence=score.total,
            size=0.0,
            reason=f"Señal bajista ({bearish_signals}/3) — sin operación larga disponible",
            symbol=symbol,
            score=score,
        )
    else:
        return EvaluationResult(
            decision=Decision.NO_SIGNAL,
            action="none",
            confidence=score.total,
            size=0.0,
            reason=f"Señales mixtas (bullish={bullish_signals} bearish={bearish_signals})",
            symbol=symbol,
            score=score,
        )

    # ── Tamaño dinámico según confianza ─────────────────────────────────────
    # Score 0.65–0.75 → size 0.05
    # Score 0.75–0.85 → size 0.10
    # Score > 0.85    → size 0.15
    if score.total >= 0.85:
        size = 0.15
    elif score.total >= 0.75:
        size = 0.10
    else:
        size = 0.05

    logger.info(f"APPROVE [{symbol}]: {action.upper()} | confidence={score.total:.3f} | size={size}")

    return EvaluationResult(
        decision=Decision.APPROVE,
        action=action,
        confidence=score.total,
        size=size,
        reason=reason,
        symbol=symbol,
        score=score,
    )
