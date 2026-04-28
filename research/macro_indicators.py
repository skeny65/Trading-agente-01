import logging
from dataclasses import dataclass
from datetime import datetime

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

_FEAR_GREED_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


@dataclass
class MacroContext:
    fear_greed_score: float      # 0–100  (0=extreme fear, 100=extreme greed)
    fear_greed_label: str        # "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed"
    vix: float                   # índice de volatilidad (bajo < 15, alto > 25)
    vix_regime: str              # "low" | "moderate" | "high" | "extreme"
    macro_bias: str              # "bullish" | "neutral" | "bearish"
    fetched_at: str


def _fetch_fear_greed() -> tuple[float, str]:
    try:
        r = requests.get(_FEAR_GREED_URL, headers=_HEADERS, timeout=8)
        r.raise_for_status()
        score = float(r.json()["fear_and_greed"]["score"])
        label = _fear_greed_label(score)
        return score, label
    except Exception as e:
        logger.warning(f"Fear & Greed no disponible: {e}")
        return 50.0, "Neutral"


def _fetch_vix() -> float:
    try:
        hist = yf.Ticker("^VIX").history(period="2d")
        if hist.empty:
            return 20.0
        return round(float(hist["Close"].iloc[-1]), 2)
    except Exception as e:
        logger.warning(f"VIX no disponible: {e}")
        return 20.0


def _fear_greed_label(score: float) -> str:
    if score <= 25:
        return "Extreme Fear"
    if score <= 40:
        return "Fear"
    if score <= 60:
        return "Neutral"
    if score <= 75:
        return "Greed"
    return "Extreme Greed"


def _vix_regime(vix: float) -> str:
    if vix < 15:
        return "low"
    if vix < 20:
        return "moderate"
    if vix < 30:
        return "high"
    return "extreme"


def _macro_bias(fg_score: float, vix: float) -> str:
    # Greed + VIX bajo → mercado confiado → bullish
    # Fear + VIX alto  → mercado estresado → bearish
    bullish_pts = 0
    bearish_pts = 0

    if fg_score >= 60:
        bullish_pts += 1
    elif fg_score <= 40:
        bearish_pts += 1

    if vix < 20:
        bullish_pts += 1
    elif vix > 25:
        bearish_pts += 1

    if bullish_pts > bearish_pts:
        return "bullish"
    if bearish_pts > bullish_pts:
        return "bearish"
    return "neutral"


def get_macro_context() -> MacroContext:
    fg_score, fg_label = _fetch_fear_greed()
    vix = _fetch_vix()
    vix_reg = _vix_regime(vix)
    bias = _macro_bias(fg_score, vix)

    ctx = MacroContext(
        fear_greed_score=round(fg_score, 1),
        fear_greed_label=fg_label,
        vix=vix,
        vix_regime=vix_reg,
        macro_bias=bias,
        fetched_at=datetime.utcnow().isoformat(),
    )

    logger.info(
        f"Macro: Fear&Greed={fg_score:.0f} ({fg_label}) "
        f"| VIX={vix} ({vix_reg}) | bias={bias}"
    )
    return ctx
