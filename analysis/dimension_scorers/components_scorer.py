"""
Scorer de la dimensión Componentes (peso 20%).
Combina: salud de top 10 holdings + breadth sectorial + earnings momentum.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ComponentsScore:
    top10_score: float
    sector_score: float
    total: float
    earnings_veto: bool   # True si hay ≥3 earnings de top 10 en 48h
    label: str


def calculate(
    top10_score: float,
    sector_score: float,
    earnings_veto: bool = False,
) -> ComponentsScore:
    """
    Pesos internos:
      top 10 holdings 60% | breadth sectorial 40%
    """
    total = round(
        top10_score   * 0.60
        + sector_score * 0.40,
        4,
    )
    total = max(0.0, min(1.0, total))

    if earnings_veto:
        total = 0.0   # veto de earnings suprime el score

    label = "bullish" if total >= 0.65 else ("neutral" if total >= 0.45 else "bearish")

    logger.info(
        f"ComponentsScore: top10={top10_score:.2f} sector={sector_score:.2f} "
        f"→ total={total:.3f} ({label})"
        + (" [EARNINGS_VETO]" if earnings_veto else "")
    )
    return ComponentsScore(
        top10_score=top10_score,
        sector_score=sector_score,
        total=total,
        earnings_veto=earnings_veto,
        label=label,
    )
