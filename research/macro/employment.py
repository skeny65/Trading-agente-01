"""
Datos de empleo: NFP, tasa de desempleo y jobless claims vía FRED API.
"""
import logging
from dataclasses import dataclass

from research.macro.fred_client import get_latest_value, get_series

logger = logging.getLogger(__name__)

_UNEMPLOYMENT_SERIES  = "UNRATE"    # Tasa de desempleo (mensual)
_JOBLESS_CLAIMS_SERIES = "IC4WSA"   # Initial claims 4-week moving average (semanal)
_PAYEMS_SERIES         = "PAYEMS"   # Non-Farm Payrolls total (mensual)


@dataclass
class EmploymentData:
    unemployment_rate: float | None   # %
    jobless_claims_4w: float | None   # miles, media 4 semanas
    nfp_mom_change: float | None      # cambio mensual en miles
    score: float                      # 0.0–1.0
    label: str                        # "strong" | "healthy" | "weakening" | "weak"


def _nfp_monthly_change() -> float | None:
    obs = get_series(_PAYEMS_SERIES, limit=3)
    if len(obs) < 2:
        return None
    latest   = obs[0]["value"]
    previous = obs[1]["value"]
    if latest is None or previous is None:
        return None
    return round(latest - previous, 1)  # en miles


def get_employment_data() -> EmploymentData:
    unemployment = get_latest_value(_UNEMPLOYMENT_SERIES)
    claims_4w    = get_latest_value(_JOBLESS_CLAIMS_SERIES)
    nfp_change   = _nfp_monthly_change()

    # Score basado en tasa de desempleo
    if unemployment is None:
        score, label = 0.5, "unknown"
    elif unemployment <= 4.0:
        score, label = 0.85, "strong"
    elif unemployment <= 5.0:
        score, label = 0.65, "healthy"
    elif unemployment <= 6.5:
        score, label = 0.40, "weakening"
    else:
        score, label = 0.15, "weak"

    # Penalización si jobless claims están elevados (>250k = señal de estrés)
    if claims_4w is not None and claims_4w > 280_000:
        score = max(0.0, score - 0.15)
        label = "weakening" if label == "healthy" else label

    logger.info(
        f"Empleo: desempleo={unemployment}% | claims4w={claims_4w} | "
        f"NFP_change={nfp_change}k | score={score:.2f} ({label})"
    )
    return EmploymentData(
        unemployment_rate=unemployment,
        jobless_claims_4w=claims_4w,
        nfp_mom_change=nfp_change,
        score=score,
        label=label,
    )
