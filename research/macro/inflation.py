"""
Datos de inflación: CPI y Core PCE vía FRED API.
"""
import logging
from dataclasses import dataclass

from research.macro.fred_client import get_latest_value, get_series

logger = logging.getLogger(__name__)

# Series FRED
_CPI_SERIES      = "CPIAUCSL"   # CPI All Urban Consumers (mensual)
_CORE_PCE_SERIES = "PCEPILFE"   # Core PCE (preferido por la Fed, mensual)


@dataclass
class InflationData:
    cpi_yoy: float | None       # variación interanual CPI %
    core_pce: float | None      # nivel Core PCE más reciente
    core_pce_yoy: float | None  # variación interanual Core PCE %
    score: float                # 0.0–1.0 (1.0 = inflación bajo control, tendiendo a 2%)
    label: str                  # "controlled" | "elevated" | "high"


def _yoy_change(series_id: str) -> float | None:
    """Calcula variación YoY del último valor respecto a 12 meses atrás."""
    obs = get_series(series_id, limit=14)
    if len(obs) < 13:
        return None
    latest = obs[0]["value"]
    year_ago = obs[12]["value"]
    if latest is None or year_ago is None or year_ago == 0:
        return None
    return round((latest - year_ago) / year_ago * 100, 2)


def get_inflation_data() -> InflationData:
    cpi_yoy      = _yoy_change(_CPI_SERIES)
    core_pce     = get_latest_value(_CORE_PCE_SERIES)
    core_pce_yoy = _yoy_change(_CORE_PCE_SERIES)

    # Score: cuánto se acerca al objetivo del 2% de la Fed
    # CPI YoY cercano a 2% = score alto / alejado = score bajo
    reference = core_pce_yoy if core_pce_yoy is not None else cpi_yoy

    if reference is None:
        score, label = 0.5, "unknown"
    elif reference <= 2.5:
        score, label = 0.85, "controlled"
    elif reference <= 3.5:
        score, label = 0.60, "elevated"
    elif reference <= 5.0:
        score, label = 0.35, "high"
    else:
        score, label = 0.10, "very_high"

    logger.info(f"Inflación: CPI YoY={cpi_yoy}% | CorePCE YoY={core_pce_yoy}% | score={score:.2f} ({label})")
    return InflationData(
        cpi_yoy=cpi_yoy,
        core_pce=core_pce,
        core_pce_yoy=core_pce_yoy,
        score=score,
        label=label,
    )
