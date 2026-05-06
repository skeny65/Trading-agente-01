"""
Estructura de plazos del VIX: VIX9D (corto), VIX (spot), VIX3M (3 meses).
Contango = calma (normal). Backwardation = estrés agudo.
"""
import logging
from dataclasses import dataclass

from research import yf_client

logger = logging.getLogger(__name__)


@dataclass
class VixTermData:
    vix9d: float | None    # VIX a 9 días
    vix:   float | None    # VIX spot (30 días)
    vix3m: float | None    # VIX a 3 meses
    structure: str         # "contango" | "backwardation" | "flat" | "unknown"
    score: float           # 1.0 = contango (calma) / 0.0 = backwardation extremo


def get_vix_term_structure() -> VixTermData:
    raw = yf_client.safe_download(
        ["^VIX9D", "^VIX", "^VIX3M"],
        period="2d", interval="1d", progress=False, auto_adjust=False,
    )
    if raw is None:
        return VixTermData(vix9d=None, vix=None, vix3m=None, structure="unknown", score=0.5)

    try:
        close = raw["Close"] if "Close" in raw else raw

        def last(sym: str) -> float | None:
            try:
                return float(close[sym].dropna().iloc[-1])
            except Exception:
                return None

        vix9d = last("^VIX9D")
        vix   = last("^VIX")
        vix3m = last("^VIX3M")
    except Exception as exc:
        logger.debug(f"VIX term structure parse error: {exc}")
        return VixTermData(vix9d=None, vix=None, vix3m=None, structure="unknown", score=0.5)

    # Determinar estructura
    if vix9d and vix and vix3m:
        if vix9d < vix < vix3m:
            structure = "contango"   # normal, mercado calmado
        elif vix9d > vix:
            structure = "backwardation"  # estrés agudo
        else:
            structure = "flat"
    elif vix9d and vix:
        structure = "contango" if vix9d < vix else "backwardation"
    else:
        structure = "unknown"

    score_map = {"contango": 0.85, "flat": 0.55, "backwardation": 0.20, "unknown": 0.50}
    score = score_map.get(structure, 0.50)

    vix3m_str = f"{vix3m:.1f}" if vix3m else "N/A"
    logger.info(
        f"VIX term: 9D={vix9d:.1f} spot={vix:.1f} 3M={vix3m_str} "
        f"| estructura={structure} | score={score:.2f}"
        if vix9d and vix else f"VIX term: datos parciales | score={score:.2f}"
    )
    return VixTermData(vix9d=vix9d, vix=vix, vix3m=vix3m, structure=structure, score=score)
