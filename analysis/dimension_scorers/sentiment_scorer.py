"""
Scorer de la dimensión Sentimiento (peso 15%).
Combina: Fear&Greed, VIX term structure, Put/Call ratio, VADER de noticias.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SentimentScore:
    fear_greed_score: float
    vix_term_score: float
    put_call_score: float
    news_score: float
    total: float
    label: str


def calculate(
    fear_greed_score: float,     # 0–1 (ya normalizado desde 0–100)
    vix_term_score: float,       # 0–1 de vix_term_structure
    put_call_score: float,       # 0–1 de put_call_ratio
    news_sentiment_score: float, # 0–1 de VADER (compound+1)/2
) -> SentimentScore:
    """
    Pesos internos:
      Fear&Greed 30% | VIX term structure 25% | Put/Call 20% | VADER noticias 25%
    """
    total = round(
        fear_greed_score      * 0.30
        + vix_term_score      * 0.25
        + put_call_score      * 0.20
        + news_sentiment_score * 0.25,
        4,
    )
    total = max(0.0, min(1.0, total))
    label = "bullish" if total >= 0.65 else ("neutral" if total >= 0.45 else "bearish")

    logger.info(
        f"SentimentScore: fg={fear_greed_score:.2f} vix_term={vix_term_score:.2f} "
        f"pc={put_call_score:.2f} news={news_sentiment_score:.2f} → total={total:.3f} ({label})"
    )
    return SentimentScore(
        fear_greed_score=fear_greed_score,
        vix_term_score=vix_term_score,
        put_call_score=put_call_score,
        news_score=news_sentiment_score,
        total=total,
        label=label,
    )
