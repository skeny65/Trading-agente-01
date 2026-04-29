"""
Scorer de la dimensión Eventos (peso 10%).
Refleja el riesgo de eventos programados (FOMC, CPI, NFP) en las próximas 48h.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EventsScore:
    score_multiplier: float   # del get_defensive_mode()
    veto: bool
    geopolitics_score: float
    total: float
    reason: str


def calculate(
    score_multiplier: float,  # 0.0 (veto) / 0.5 / 0.85 / 1.0
    veto: bool,
    geopolitics_score: float,  # 0.0–1.0 de geopolitics_news
    reason: str = "",
) -> EventsScore:
    if veto:
        total = 0.0
    else:
        # calendar_score: transformar multiplicador en score 0–1
        # 1.0 → 1.0 | 0.85 → 0.70 | 0.50 → 0.40 | 0.0 → 0.0
        calendar_score = score_multiplier
        total = round(
            calendar_score    * 0.60
            + geopolitics_score * 0.40,
            4,
        )
        total = max(0.0, min(1.0, total))

    logger.info(
        f"EventsScore: multiplier={score_multiplier:.2f} geo={geopolitics_score:.2f} "
        f"→ total={total:.3f}"
        + (f" [VETO: {reason}]" if veto else f" ({reason})")
    )
    return EventsScore(
        score_multiplier=score_multiplier,
        veto=veto,
        geopolitics_score=geopolitics_score,
        total=total,
        reason=reason,
    )
