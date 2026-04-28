import logging
from dataclasses import dataclass
from datetime import datetime

import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class Quote:
    symbol: str
    price: float
    prev_close: float
    change_pct: float        # % cambio respecto al cierre anterior
    volume: int
    avg_volume: int
    volume_ratio: float      # volume / avg_volume
    sma20: float
    price_vs_sma20: float    # % que el precio está por encima/debajo de SMA20
    trend: str               # "bullish" | "bearish" | "neutral"
    fetched_at: str


def get_quote(symbol: str) -> Quote | None:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="30d")

        if hist.empty or len(hist) < 5:
            logger.warning(f"{symbol}: historial insuficiente")
            return None

        price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        change_pct = ((price - prev_close) / prev_close) * 100

        volume = int(hist["Volume"].iloc[-1])
        avg_volume = int(hist["Volume"].mean())
        volume_ratio = volume / avg_volume if avg_volume > 0 else 1.0

        sma20 = float(hist["Close"].tail(20).mean())
        price_vs_sma20 = ((price - sma20) / sma20) * 100

        if price_vs_sma20 > 1.0:
            trend = "bullish"
        elif price_vs_sma20 < -1.0:
            trend = "bearish"
        else:
            trend = "neutral"

        return Quote(
            symbol=symbol,
            price=price,
            prev_close=prev_close,
            change_pct=round(change_pct, 2),
            volume=volume,
            avg_volume=avg_volume,
            volume_ratio=round(volume_ratio, 2),
            sma20=round(sma20, 2),
            price_vs_sma20=round(price_vs_sma20, 2),
            trend=trend,
            fetched_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"{symbol}: error obteniendo quote — {e}")
        return None


def get_quotes(symbols: list[str]) -> dict[str, Quote]:
    results = {}
    for symbol in symbols:
        quote = get_quote(symbol)
        if quote:
            results[symbol] = quote
            logger.info(
                f"{symbol}: ${quote.price:.2f} ({quote.change_pct:+.2f}%) "
                f"| trend={quote.trend} | vol_ratio={quote.volume_ratio:.2f}x"
            )
    return results
