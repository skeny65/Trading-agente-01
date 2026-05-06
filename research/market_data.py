import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import config
from research import yf_client

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    symbol: str
    price: float
    prev_close: float
    change_pct: float
    volume: int
    avg_volume: int
    volume_ratio: float
    sma20: float
    sma50: float
    price_vs_sma20: float
    trend: str           # "bullish" | "bearish" | "neutral"
    trend_strength: str  # "strong_bullish" | "bullish" | "neutral" | "bearish" | "strong_bearish"
    fetched_at: str


def get_quote(symbol: str) -> "Quote | None":
    hist = yf_client.safe_history(symbol, period=f"{config.PRICE_HISTORY_DAYS}d")
    if hist is None or len(hist) < 21:
        return None

    try:
        price      = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = ((price - prev_close) / prev_close) * 100

        volume     = int(hist["Volume"].iloc[-1])
        avg_volume = int(hist["Volume"].mean())
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        sma20 = float(hist["Close"].tail(20).mean())
        sma50 = float(hist["Close"].tail(50).mean()) if len(hist) >= 50 else sma20

        price_vs_sma20 = ((price - sma20) / sma20) * 100

        if price_vs_sma20 > 1.0:
            trend = "bullish"
        elif price_vs_sma20 < -1.0:
            trend = "bearish"
        else:
            trend = "neutral"

        if price > sma20 and sma20 > sma50:
            trend_strength = "strong_bullish"
        elif price > sma20:
            trend_strength = "bullish"
        elif price < sma20 and sma20 < sma50:
            trend_strength = "strong_bearish"
        elif price < sma20:
            trend_strength = "bearish"
        else:
            trend_strength = "neutral"

        quote = Quote(
            symbol=symbol,
            price=round(price, 2),
            prev_close=round(prev_close, 2),
            change_pct=round(change_pct, 2),
            volume=volume,
            avg_volume=avg_volume,
            volume_ratio=round(volume_ratio, 2),
            sma20=round(sma20, 2),
            sma50=round(sma50, 2),
            price_vs_sma20=round(price_vs_sma20, 2),
            trend=trend,
            trend_strength=trend_strength,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            f"{symbol}: ${quote.price:.2f} ({quote.change_pct:+.2f}%) "
            f"| SMA20=${quote.sma20:.2f} SMA50=${quote.sma50:.2f} "
            f"| trend={quote.trend_strength} | vol_ratio={quote.volume_ratio:.2f}x"
        )
        return quote

    except Exception as e:
        logger.error(f"{symbol}: error procesando quote — {e}")
        return None


def get_quotes(symbols: list[str]) -> dict[str, "Quote"]:
    results = {}
    for symbol in symbols:
        quote = get_quote(symbol)
        if quote:
            results[symbol] = quote
    return results
