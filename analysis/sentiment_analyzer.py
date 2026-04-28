import logging
from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from research.news_fetcher import Headline

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()


@dataclass
class SentimentResult:
    compound: float      # -1.0 a +1.0 (promedio ponderado de titulares)
    positive_ratio: float  # % de titulares positivos
    negative_ratio: float  # % de titulares negativos
    headline_count: int
    label: str           # "positive" | "neutral" | "negative"


def analyze(headlines: list[Headline]) -> SentimentResult:
    if not headlines:
        return SentimentResult(
            compound=0.0,
            positive_ratio=0.0,
            negative_ratio=0.0,
            headline_count=0,
            label="neutral",
        )

    scores = []
    for h in headlines:
        text = f"{h.title}. {h.description}"
        score = _analyzer.polarity_scores(text)["compound"]
        scores.append(score)

    compound = sum(scores) / len(scores)
    positive_ratio = sum(1 for s in scores if s >= 0.05) / len(scores)
    negative_ratio = sum(1 for s in scores if s <= -0.05) / len(scores)

    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    logger.info(
        f"Sentiment: compound={compound:.3f} ({label}) "
        f"| pos={positive_ratio:.0%} neg={negative_ratio:.0%} "
        f"| n={len(headlines)}"
    )

    return SentimentResult(
        compound=round(compound, 3),
        positive_ratio=round(positive_ratio, 3),
        negative_ratio=round(negative_ratio, 3),
        headline_count=len(headlines),
        label=label,
    )
