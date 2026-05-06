"""
Performance de los top 10 holdings de SPY (pesan ~35% del ETF).
Fuentes: Yahoo Finance + Twelve Data simultáneos. Pesos estáticos (actualizar si cambian significativamente).
"""
import logging
from dataclasses import dataclass

import pandas as pd

from research import yf_client, td_client

logger = logging.getLogger(__name__)

# Top 10 holdings SPY con pesos aproximados (validar en ssga.com/spy)
SPY_TOP_10: list[dict] = [
    {"symbol": "AAPL",  "weight": 0.070, "name": "Apple"},
    {"symbol": "MSFT",  "weight": 0.067, "name": "Microsoft"},
    {"symbol": "NVDA",  "weight": 0.062, "name": "Nvidia"},
    {"symbol": "AMZN",  "weight": 0.035, "name": "Amazon"},
    {"symbol": "META",  "weight": 0.025, "name": "Meta"},
    {"symbol": "GOOGL", "weight": 0.020, "name": "Alphabet A"},
    {"symbol": "GOOG",  "weight": 0.018, "name": "Alphabet C"},
    {"symbol": "BRK-B", "weight": 0.017, "name": "Berkshire"},
    {"symbol": "TSLA",  "weight": 0.015, "name": "Tesla"},
    {"symbol": "LLY",   "weight": 0.013, "name": "Eli Lilly"},
]


@dataclass
class HoldingPerf:
    symbol: str
    weight: float
    change_1d: float | None    # % change last day
    change_5d: float | None    # % change last 5 days
    above_sma20: bool | None


@dataclass
class TopHoldingsData:
    holdings: list[HoldingPerf]
    weighted_avg_1d: float | None   # retorno ponderado 1d (proxy del impacto en SPY)
    bullish_count: int              # cuántos de los top 10 están verdes en 1d
    score: float                    # 0.0–1.0


def get_top_holdings_data() -> TopHoldingsData:
    symbols = [h["symbol"] for h in SPY_TOP_10]
    weights = {h["symbol"]: h["weight"] for h in SPY_TOP_10}

    # Ambas fuentes corren simultáneamente
    raw = yf_client.safe_download(symbols, period="30d", interval="1d",
                                   progress=False, auto_adjust=True)

    if not td_client.is_blocked() and td_client.remaining_calls() >= len(symbols):
        td_results = td_client.safe_batch_close(symbols, interval="1day", outputsize=30)
    else:
        td_results = {}

    # Construir DataFrame combinado: Yahoo base + TD rellena símbolos que faltan
    if raw is not None:
        try:
            yf_close = raw["Close"] if "Close" in raw else raw
        except Exception:
            yf_close = pd.DataFrame()
    else:
        yf_close = pd.DataFrame()
        logger.info("Top holdings: Yahoo no disponible — usando sólo Twelve Data")

    td_frames: dict = {}
    for sym, df in td_results.items():
        if df is not None and "Close" in df:
            if sym not in yf_close.columns:
                td_frames[sym] = df["Close"]

    if td_frames:
        td_df = pd.DataFrame(td_frames)
        close = pd.concat([yf_close, td_df], axis=1) if not yf_close.empty else td_df
    else:
        close = yf_close

    if close.empty:
        logger.warning("Top holdings: sin datos en Yahoo ni Twelve Data — score neutral 0.5")
        return TopHoldingsData(holdings=[], weighted_avg_1d=None, bullish_count=0, score=0.5)

    holdings: list[HoldingPerf] = []
    weighted_sum = 0.0
    total_weight = 0.0
    bullish_count = 0

    for item in SPY_TOP_10:
        sym = item["symbol"]
        try:
            prices = close[sym].dropna()
            if len(prices) < 2:
                continue
            chg_1d = float((prices.iloc[-1] / prices.iloc[-2] - 1) * 100)
            chg_5d = float((prices.iloc[-1] / prices.iloc[-6] - 1) * 100) if len(prices) >= 6 else None
            sma20  = float(prices.iloc[-20:].mean()) if len(prices) >= 20 else None
            above_sma20 = bool(float(prices.iloc[-1]) > sma20) if sma20 else None

            w = weights.get(sym, 0.0)
            weighted_sum += chg_1d * w
            total_weight += w
            if chg_1d > 0:
                bullish_count += 1

            holdings.append(HoldingPerf(
                symbol=sym, weight=w,
                change_1d=round(chg_1d, 3),
                change_5d=round(chg_5d, 3) if chg_5d else None,
                above_sma20=above_sma20,
            ))
        except Exception as exc:
            logger.debug(f"{sym}: {exc}")

    weighted_avg = round(weighted_sum / total_weight, 4) if total_weight > 0 else None

    # Score basado en qué fracción de los top 10 están verdes y el retorno ponderado
    if not holdings:
        score = 0.5
    else:
        breadth_score = bullish_count / len(holdings)
        # retorno ponderado positivo = señal alcista
        return_score = 0.5 + min(0.4, max(-0.4, (weighted_avg or 0) * 10))
        score = breadth_score * 0.60 + return_score * 0.40

    logger.info(
        f"Top10 holdings: {bullish_count}/{len(holdings)} alcistas | "
        f"retorno_pond={weighted_avg:+.3f}% | score={score:.2f}"
        if weighted_avg is not None else
        f"Top10 holdings: {bullish_count}/{len(holdings)} alcistas | score={score:.2f}"
    )
    return TopHoldingsData(
        holdings=holdings,
        weighted_avg_1d=weighted_avg,
        bullish_count=bullish_count,
        score=score,
    )
