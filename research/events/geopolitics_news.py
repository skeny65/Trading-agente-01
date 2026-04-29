"""
Noticias geopolíticas de alto impacto vía Reuters RSS y NewsAPI.
Complementa el calendario económico con eventos no programados.
"""
import logging
from dataclasses import dataclass

import requests

import config
from research.news_fetcher import fetch as fetch_headlines

logger = logging.getLogger(__name__)

_REUTERS_RSS = "https://feeds.reuters.com/reuters/businessNews"
_TIMEOUT     = 8

_GEOPOLITICAL_KEYWORDS = [
    "war", "guerra", "military", "conflict", "sanction", "tariff", "arancel",
    "trade war", "shutdown", "debt ceiling", "default", "recession", "crash",
    "bank failure", "systemic risk", "pandemic", "lockdown",
]


@dataclass
class GeopoliticsSignal:
    risk_level: str    # "low" | "medium" | "high" | "extreme"
    headlines: list[str]
    score: float       # 0.0 = máximo riesgo, 1.0 = sin riesgo


def _count_risk_headlines(headlines: list[str]) -> int:
    count = 0
    for h in headlines:
        h_lower = h.lower()
        if any(kw in h_lower for kw in _GEOPOLITICAL_KEYWORDS):
            count += 1
    return count


def get_geopolitics_signal() -> GeopoliticsSignal:
    """
    Obtiene titulares de Reuters/NewsAPI sobre SPY/mercados y detecta
    señales geopolíticas de riesgo. Fallback a "low" si las fuentes fallan.
    """
    headlines: list[str] = []

    # Intentar NewsAPI con query de mercado + riesgo
    try:
        market_headlines = fetch_headlines(
            symbol="SPY",
            hours=config.NEWS_LOOKBACK_HOURS,
        )
        headlines.extend(market_headlines)
    except Exception as exc:
        logger.debug(f"NewsAPI geopolítica: {exc}")

    # Reuters RSS como fuente adicional
    try:
        resp = requests.get(_REUTERS_RSS, timeout=_TIMEOUT,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        import re
        titles = re.findall(r"<title><!\[CDATA\[(.+?)\]\]></title>", resp.text)
        headlines.extend(titles[:10])
    except Exception as exc:
        logger.debug(f"Reuters RSS: {exc}")

    if not headlines:
        return GeopoliticsSignal(risk_level="low", headlines=[], score=0.80)

    risk_count = _count_risk_headlines(headlines)
    ratio = risk_count / len(headlines)

    if ratio >= 0.50:
        risk_level, score = "extreme", 0.10
    elif ratio >= 0.30:
        risk_level, score = "high", 0.30
    elif ratio >= 0.15:
        risk_level, score = "medium", 0.60
    else:
        risk_level, score = "low", 0.85

    logger.info(
        f"Geopolítica: {risk_count}/{len(headlines)} titulares de riesgo "
        f"| nivel={risk_level} | score={score:.2f}"
    )
    return GeopoliticsSignal(
        risk_level=risk_level,
        headlines=headlines[:5],
        score=score,
    )
