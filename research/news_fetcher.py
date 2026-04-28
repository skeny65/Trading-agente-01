import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

import config

logger = logging.getLogger(__name__)

_BASE_URL = "https://newsapi.org/v2/everything"


@dataclass
class Headline:
    title: str
    description: str
    source: str
    published_at: str


def fetch(symbol: str, hours: int = 6) -> list[Headline]:
    if not config.NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY no configurado — sin noticias")
        return []

    try:
        r = requests.get(
            _BASE_URL,
            params={
                "q": symbol,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": config.NEWSAPI_KEY,
            },
            timeout=10,
        )
        r.raise_for_status()
        articles = r.json().get("articles", [])

        cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
        results: list[Headline] = []

        for a in articles:
            pub = a.get("publishedAt", "")
            try:
                ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).timestamp()
                if ts < cutoff:
                    continue
            except Exception:
                pass

            results.append(
                Headline(
                    title=a.get("title") or "",
                    description=a.get("description") or "",
                    source=a.get("source", {}).get("name", ""),
                    published_at=pub,
                )
            )

        logger.info(f"{symbol}: {len(results)} titulares en las últimas {hours}h")
        return results

    except Exception as e:
        logger.error(f"NewsAPI error para {symbol}: {e}")
        return []


def fetch_all(symbols: list[str], hours: int = 6) -> dict[str, list[Headline]]:
    return {symbol: fetch(symbol, hours) for symbol in symbols}
