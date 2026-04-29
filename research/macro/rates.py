"""
Tasas de interés y curva de rendimientos vía FRED API.
Serie clave: Fed Funds Rate, 10Y Treasury, 2Y Treasury, spread 10Y-2Y.
"""
import logging
from dataclasses import dataclass

from research.macro.fred_client import get_latest_value

logger = logging.getLogger(__name__)

_FED_FUNDS_SERIES  = "DFF"      # Fed Funds Rate (diario efectivo)
_YIELD_10Y_SERIES  = "DGS10"    # 10-Year Treasury Constant Maturity
_YIELD_2Y_SERIES   = "DGS2"     # 2-Year Treasury Constant Maturity
_YIELD_CURVE_SERIES = "T10Y2Y"  # Spread 10Y-2Y (precalculado por FRED)


@dataclass
class RatesData:
    fed_funds_rate: float | None   # %
    yield_10y: float | None        # %
    yield_2y: float | None         # %
    yield_curve_spread: float | None  # 10Y - 2Y en puntos básicos
    curve_shape: str               # "normal" | "flat" | "inverted"
    score: float                   # 0.0–1.0
    label: str


def get_rates_data() -> RatesData:
    fed_funds = get_latest_value(_FED_FUNDS_SERIES)
    y10       = get_latest_value(_YIELD_10Y_SERIES)
    y2        = get_latest_value(_YIELD_2Y_SERIES)
    spread    = get_latest_value(_YIELD_CURVE_SERIES)

    # Calcular spread si FRED no lo devuelve
    if spread is None and y10 is not None and y2 is not None:
        spread = round(y10 - y2, 3)

    # Clasificar forma de la curva
    if spread is None:
        curve_shape = "unknown"
    elif spread > 0.50:
        curve_shape = "normal"
    elif spread > -0.10:
        curve_shape = "flat"
    else:
        curve_shape = "inverted"

    # Score: curva normal = buena señal / invertida = recesión
    # + Fed hawkish (tasas altas) penaliza, dovish/pausa beneficia
    if curve_shape == "normal":
        base_score = 0.80
    elif curve_shape == "flat":
        base_score = 0.55
    elif curve_shape == "inverted":
        base_score = 0.30
    else:
        base_score = 0.50

    # Penalización si la curva está muy invertida (spread < -0.5)
    if spread is not None and spread < -0.50:
        base_score = max(0.10, base_score - 0.15)

    score = base_score
    label = curve_shape

    logger.info(
        f"Tasas: fed_funds={fed_funds}% | 10Y={y10}% | 2Y={y2}% | "
        f"spread={spread} ({curve_shape}) | score={score:.2f}"
    )
    return RatesData(
        fed_funds_rate=fed_funds,
        yield_10y=y10,
        yield_2y=y2,
        yield_curve_spread=spread,
        curve_shape=curve_shape,
        score=score,
        label=label,
    )
