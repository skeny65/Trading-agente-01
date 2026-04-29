"""
Scorer de la dimensión Macro (peso 25%).
Combina: inflación, empleo, tasas/yield curve, postura Fed.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MacroScore:
    inflation_score: float
    employment_score: float
    rates_score: float
    fed_score: float
    total: float          # suma ponderada — el score final de la dimensión
    veto: bool            # True si la curva está muy invertida Y trend bajista
    label: str


def calculate(
    inflation_score: float,
    employment_score: float,
    rates_score: float,
    fed_score: float,
    yield_curve_spread: float | None = None,
) -> MacroScore:
    """
    Pesos internos:
      inflación  30% | empleo 25% | tasas 30% | Fed 15%
    """
    total = (
        inflation_score  * 0.30
        + employment_score * 0.25
        + rates_score      * 0.30
        + fed_score        * 0.15
    )
    total = round(max(0.0, min(1.0, total)), 4)

    # Veto: curva MUY invertida (spread < -0.50) y macro deteriorada
    veto = bool(
        yield_curve_spread is not None
        and yield_curve_spread < -0.50
        and total < 0.35
    )

    if total >= 0.70:
        label = "bullish"
    elif total >= 0.50:
        label = "neutral"
    else:
        label = "bearish"

    logger.info(
        f"MacroScore: inflation={inflation_score:.2f} employment={employment_score:.2f} "
        f"rates={rates_score:.2f} fed={fed_score:.2f} → total={total:.3f} ({label})"
        + (" [VETO]" if veto else "")
    )
    return MacroScore(
        inflation_score=inflation_score,
        employment_score=employment_score,
        rates_score=rates_score,
        fed_score=fed_score,
        total=total,
        veto=veto,
        label=label,
    )
