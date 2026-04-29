"""
Breadth sectorial del S&P 500 usando los 11 ETFs sectoriales SPDR.
Cuántos sectores están en verde y cuál lidera/rezaga.
"""
import logging
from dataclasses import dataclass

import yfinance as yf

logger = logging.getLogger(__name__)

SECTOR_ETFS: list[dict] = [
    {"symbol": "XLK",  "sector": "Technology"},
    {"symbol": "XLF",  "sector": "Financials"},
    {"symbol": "XLV",  "sector": "Healthcare"},
    {"symbol": "XLY",  "sector": "Consumer Disc."},
    {"symbol": "XLP",  "sector": "Consumer Staples"},
    {"symbol": "XLI",  "sector": "Industrials"},
    {"symbol": "XLE",  "sector": "Energy"},
    {"symbol": "XLU",  "sector": "Utilities"},
    {"symbol": "XLB",  "sector": "Materials"},
    {"symbol": "XLRE", "sector": "Real Estate"},
    {"symbol": "XLC",  "sector": "Comm. Services"},
]


@dataclass
class SectorPerf:
    symbol: str
    sector: str
    change_1d: float | None
    change_5d: float | None


@dataclass
class SectorBreadthData:
    sectors: list[SectorPerf]
    green_count: int            # sectores positivos en 1d
    total_count: int
    breadth_ratio: float        # green_count / total_count
    leading_sector: str | None  # mejor sector en 5d
    lagging_sector: str | None  # peor sector en 5d
    tech_leading: bool          # True si XLK está liderando (bullish para SPY)
    score: float                # 0.0–1.0


def get_sector_breadth() -> SectorBreadthData:
    symbols = [s["symbol"] for s in SECTOR_ETFS]
    sector_map = {s["symbol"]: s["sector"] for s in SECTOR_ETFS}

    try:
        raw   = yf.download(symbols, period="10d", interval="1d",
                            progress=False, auto_adjust=True)
        close = raw["Close"] if "Close" in raw else raw
    except Exception as exc:
        logger.warning(f"Sector breadth error: {exc}")
        return SectorBreadthData(
            sectors=[], green_count=0, total_count=0,
            breadth_ratio=0.5, leading_sector=None,
            lagging_sector=None, tech_leading=False, score=0.5,
        )

    perfs: list[SectorPerf] = []
    for sym in symbols:
        try:
            prices = close[sym].dropna()
            if len(prices) < 2:
                continue
            chg_1d = float((prices.iloc[-1] / prices.iloc[-2] - 1) * 100)
            chg_5d = float((prices.iloc[-1] / prices.iloc[-6] - 1) * 100) if len(prices) >= 6 else None
            perfs.append(SectorPerf(
                symbol=sym, sector=sector_map[sym],
                change_1d=round(chg_1d, 3),
                change_5d=round(chg_5d, 3) if chg_5d else None,
            ))
        except Exception:
            pass

    if not perfs:
        return SectorBreadthData(
            sectors=[], green_count=0, total_count=0,
            breadth_ratio=0.5, leading_sector=None,
            lagging_sector=None, tech_leading=False, score=0.5,
        )

    green_count    = sum(1 for p in perfs if p.change_1d and p.change_1d > 0)
    breadth_ratio  = green_count / len(perfs)
    perfs_5d       = [p for p in perfs if p.change_5d is not None]
    leading_sector = max(perfs_5d, key=lambda p: p.change_5d).sector if perfs_5d else None
    lagging_sector = min(perfs_5d, key=lambda p: p.change_5d).sector if perfs_5d else None
    xlk_perf       = next((p for p in perfs if p.symbol == "XLK"), None)
    tech_leading   = bool(xlk_perf and xlk_perf.change_5d and xlk_perf.change_5d > 0)

    # Score: breadth amplia + tech liderando = bullish
    score = breadth_ratio * 0.70 + (0.30 if tech_leading else 0.0)

    logger.info(
        f"Sectores: {green_count}/{len(perfs)} verdes | "
        f"líder={leading_sector} | rezagado={lagging_sector} | score={score:.2f}"
    )
    return SectorBreadthData(
        sectors=perfs,
        green_count=green_count,
        total_count=len(perfs),
        breadth_ratio=breadth_ratio,
        leading_sector=leading_sector,
        lagging_sector=lagging_sector,
        tech_leading=tech_leading,
        score=score,
    )
