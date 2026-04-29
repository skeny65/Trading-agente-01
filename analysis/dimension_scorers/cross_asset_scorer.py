"""
Scorer de la dimensión Cross-Assets (peso 10%).
Envuelve CrossAssetData en un score con penalización por divergencias.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CrossAssetScore:
    base_score: float
    divergence_count: int
    total: float
    label: str


def calculate(
    cross_asset_score: float,   # score ya calculado en correlations.py
    divergences: list[str],
) -> CrossAssetScore:
    # Cada divergencia detectada penaliza el score
    penalty = len(divergences) * 0.10
    total   = max(0.0, min(1.0, cross_asset_score - penalty))
    total   = round(total, 4)
    label   = "bullish" if total >= 0.60 else ("neutral" if total >= 0.40 else "bearish")

    if divergences:
        logger.warning(
            f"CrossAssetScore: {len(divergences)} divergencias | score={total:.3f} ({label})"
        )
    else:
        logger.info(f"CrossAssetScore: sin divergencias | score={total:.3f} ({label})")

    return CrossAssetScore(
        base_score=cross_asset_score,
        divergence_count=len(divergences),
        total=total,
        label=label,
    )
