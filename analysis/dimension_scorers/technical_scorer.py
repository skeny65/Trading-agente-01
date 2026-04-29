"""
Scorer de la dimensión Técnico (peso 20%).
Envuelve el resultado de MultiTimeframeAnalysis en un score normalizado.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TechnicalScore:
    overall_score: float
    bullish_count: int     # timeframes bullish de 3
    rsi_veto: bool
    sma200_veto: bool
    atr_veto: bool
    total: float
    label: str


def calculate(
    overall_score: float,
    bullish_count: int,
    rsi_veto: bool,
    sma200_veto: bool,
    atr_veto: bool,
) -> TechnicalScore:
    # Vetos técnicos fuerzan el score a 0
    if rsi_veto or sma200_veto:
        total = 0.0
        label = "bearish"
    else:
        # Bonus por alineación de timeframes
        alignment_bonus = (bullish_count - 1) * 0.05  # +0.05 por cada TF bullish extra
        total = max(0.0, min(1.0, overall_score + alignment_bonus))
        # Penalización leve por ATR anómalo (más riesgo, no veto total)
        if atr_veto:
            total = max(0.0, total - 0.15)
        label = "bullish" if total >= 0.65 else ("neutral" if total >= 0.45 else "bearish")

    logger.info(
        f"TechnicalScore: score={overall_score:.2f} tfs={bullish_count}/3 "
        f"→ total={total:.3f} ({label})"
        + (" [RSI_VETO]" if rsi_veto else "")
        + (" [SMA200_VETO]" if sma200_veto else "")
        + (" [ATR_ANÓMALO]" if atr_veto else "")
    )
    return TechnicalScore(
        overall_score=overall_score,
        bullish_count=bullish_count,
        rsi_veto=rsi_veto,
        sma200_veto=sma200_veto,
        atr_veto=atr_veto,
        total=total,
        label=label,
    )
