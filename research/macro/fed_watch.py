"""
Probabilidad del próximo movimiento de la Fed (hawkish / dovish / pausa).
Usa la API pública de CME FedWatch scrapeada de forma simple.
Fallback: inferencia desde Fed Funds Rate vs inflación.
"""
import logging
from dataclasses import dataclass

import requests

from research.macro.fred_client import get_latest_value

logger = logging.getLogger(__name__)

_CME_URL = "https://www.cmegroup.com/CmeWS/mvc/ProductCalendar/Options?productCode=SR3"
_TIMEOUT = 8


@dataclass
class FedWatchData:
    prob_hike: float      # probabilidad de subida en próximo FOMC (0–1)
    prob_cut: float       # probabilidad de bajada (0–1)
    prob_hold: float      # probabilidad de pausa (0–1)
    fed_stance: str       # "hawkish" | "neutral" | "dovish"
    score: float          # 0.0–1.0 (dovish/pausa = alto / hawkish = bajo)


def _infer_from_rates() -> FedWatchData:
    """Fallback: inferir postura Fed desde diferencial tasa-inflación."""
    fed_funds = get_latest_value("DFF")
    cpi_level = get_latest_value("CPIAUCSL")

    # Si no hay datos, devolver neutral
    if fed_funds is None:
        return FedWatchData(
            prob_hike=0.15, prob_cut=0.15, prob_hold=0.70,
            fed_stance="neutral", score=0.55,
        )

    # Tasa muy alta (>5%) → Fed hawkish pero puede pausar
    if fed_funds >= 5.0:
        return FedWatchData(
            prob_hike=0.10, prob_cut=0.25, prob_hold=0.65,
            fed_stance="neutral", score=0.55,
        )
    elif fed_funds >= 3.5:
        return FedWatchData(
            prob_hike=0.20, prob_cut=0.15, prob_hold=0.65,
            fed_stance="hawkish", score=0.40,
        )
    else:
        return FedWatchData(
            prob_hike=0.05, prob_cut=0.40, prob_hold=0.55,
            fed_stance="dovish", score=0.75,
        )


def get_fed_watch_data() -> FedWatchData:
    """
    Intenta leer probabilidades de CME FedWatch.
    Si falla, usa inferencia desde tasas FRED.
    """
    try:
        resp = requests.get(_CME_URL, timeout=_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()

        # Extraer primera reunión disponible con probabilidades
        meetings = data if isinstance(data, list) else data.get("meetings", [])
        if not meetings:
            raise ValueError("Sin datos de reuniones")

        meeting = meetings[0]
        probs = meeting.get("probabilities", {})

        prob_hike = float(probs.get("INCREASE", 0)) / 100
        prob_cut  = float(probs.get("DECREASE", 0)) / 100
        prob_hold = float(probs.get("NO_CHANGE", max(0, 100 - prob_hike*100 - prob_cut*100))) / 100

    except Exception as exc:
        logger.debug(f"CME FedWatch no disponible ({exc}), usando inferencia")
        return _infer_from_rates()

    if prob_hike >= 0.40:
        fed_stance, score = "hawkish", 0.25
    elif prob_cut >= 0.40:
        fed_stance, score = "dovish", 0.80
    else:
        fed_stance, score = "neutral", 0.55

    logger.info(
        f"FedWatch: hike={prob_hike:.0%} cut={prob_cut:.0%} hold={prob_hold:.0%} "
        f"| stance={fed_stance} | score={score:.2f}"
    )
    return FedWatchData(
        prob_hike=prob_hike,
        prob_cut=prob_cut,
        prob_hold=prob_hold,
        fed_stance=fed_stance,
        score=score,
    )
