"""
Put/Call Ratio del CBOE. Extremos son señales contrarias.
> 1.20 = pánico (posible suelo) / < 0.70 = euforia (posible techo).
"""
import logging
import re
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

_CBOE_URL = "https://www.cboe.com/us/options/market_statistics/daily/"
_TIMEOUT  = 10


@dataclass
class PutCallData:
    ratio: float | None    # put/call ratio total equity
    signal: str            # "fear" | "greed" | "neutral"
    contrarian_bullish: bool   # True si pánico extremo (ratio > 1.20)
    contrarian_bearish: bool   # True si euforia extrema (ratio < 0.70)
    score: float           # 0.0–1.0 (contrarian: miedo = bullish)


def get_put_call_ratio() -> PutCallData:
    try:
        resp = requests.get(_CBOE_URL, timeout=_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        # Busca el equity put/call ratio en la página
        match = re.search(r"Equity.*?(\d+\.\d+)", resp.text, re.DOTALL)
        if not match:
            # Busca patrón alternativo
            match = re.search(r'"putCallRatio"\s*:\s*"?(\d+\.\d+)"?', resp.text)
        ratio = float(match.group(1)) if match else None
    except Exception as exc:
        logger.debug(f"Put/call ratio error: {exc}")
        ratio = None

    if ratio is None:
        return PutCallData(ratio=None, signal="neutral",
                           contrarian_bullish=False, contrarian_bearish=False, score=0.5)

    contrarian_bullish = ratio > 1.20
    contrarian_bearish = ratio < 0.70

    if contrarian_bullish:
        signal, score = "fear", 0.75    # pánico extremo → contrarian bullish
    elif contrarian_bearish:
        signal, score = "greed", 0.30   # euforia extrema → contrarian bearish
    elif ratio > 0.90:
        signal, score = "fear", 0.60
    else:
        signal, score = "neutral", 0.55

    logger.info(f"Put/Call ratio: {ratio:.2f} | señal={signal} | score={score:.2f}")
    return PutCallData(
        ratio=ratio,
        signal=signal,
        contrarian_bullish=contrarian_bullish,
        contrarian_bearish=contrarian_bearish,
        score=score,
    )
