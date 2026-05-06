"""
Análisis de correlaciones cruzadas de SPY con activos relacionados.
Detecta divergencias que pueden anticipar movimientos en el S&P 500.
"""
import logging
from dataclasses import dataclass

import pandas as pd

from research import yf_client, td_client

logger = logging.getLogger(__name__)

# Universo de correlación con SPY
CROSS_ASSETS = {
    "DX-Y.NYB": "DXY (Dollar)",
    "TLT":      "TLT (Bonos 20Y+)",
    "GLD":      "GLD (Oro)",
    "USO":      "USO (Petróleo)",
    "BTC-USD":  "Bitcoin",
    "HYG":      "HYG (High Yield)",
    "QQQ":      "QQQ (Nasdaq)",
}


@dataclass
class AssetSignal:
    symbol: str
    name: str
    change_1d: float | None
    change_5d: float | None


@dataclass
class CrossAssetData:
    assets: dict[str, AssetSignal]   # symbol → AssetSignal
    dxy_bullish: bool | None         # DXY subiendo (presión sobre multinacionales)
    tlt_bullish: bool | None         # TLT subiendo (flight to safety = bearish SPY)
    hyg_bullish: bool | None         # HYG subiendo (risk-on = bullish SPY)
    qqq_leading: bool | None         # QQQ superperforma SPY (bullish estructura)
    divergences: list[str]           # lista de divergencias detectadas
    score: float                     # 0.0–1.0


def _pct_change(prices, n_back: int) -> float | None:
    try:
        prices = prices.dropna()
        if len(prices) <= n_back:
            return None
        return float((prices.iloc[-1] / prices.iloc[-1 - n_back] - 1) * 100)
    except Exception:
        return None


def get_cross_asset_data(spy_change_5d: float | None = None) -> CrossAssetData:
    symbols = list(CROSS_ASSETS.keys())
    assets: dict[str, AssetSignal] = {}

    # Ambas fuentes corren simultáneamente
    raw = yf_client.safe_download(symbols, period="15d", interval="1d",
                                   progress=False, auto_adjust=True)

    if not td_client.is_blocked() and td_client.remaining_calls() >= len(symbols):
        td_results = td_client.safe_batch_close(symbols, interval="1day", outputsize=15)
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
        logger.info("Cross-assets: Yahoo no disponible — usando sólo Twelve Data")

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
        logger.warning("Cross-assets: sin datos en Yahoo ni Twelve Data — score neutral 0.5")
        return CrossAssetData(
            assets={}, dxy_bullish=None, tlt_bullish=None,
            hyg_bullish=None, qqq_leading=None,
            divergences=[], score=0.5,
        )

    for sym, name in CROSS_ASSETS.items():
        try:
            prices = close[sym]
            assets[sym] = AssetSignal(
                symbol=sym, name=name,
                change_1d=_pct_change(prices, 1),
                change_5d=_pct_change(prices, 5),
            )
        except Exception:
            assets[sym] = AssetSignal(symbol=sym, name=name, change_1d=None, change_5d=None)

    def chg5(sym: str) -> float | None:
        return assets.get(sym, AssetSignal(sym, sym, None, None)).change_5d

    dxy_chg  = chg5("DX-Y.NYB")
    tlt_chg  = chg5("TLT")
    hyg_chg  = chg5("HYG")
    qqq_chg  = chg5("QQQ")

    dxy_bullish = bool(dxy_chg and dxy_chg > 0.3)
    tlt_bullish = bool(tlt_chg and tlt_chg > 0)
    hyg_bullish = bool(hyg_chg and hyg_chg > 0)
    qqq_leading = bool(
        qqq_chg is not None and spy_change_5d is not None
        and qqq_chg > spy_change_5d + 0.5
    )

    divergences: list[str] = []

    # SPY sube pero DXY también (presión sobre multinacionales)
    if spy_change_5d and spy_change_5d > 0.5 and dxy_bullish:
        divergences.append("SPY+DXY: multinacionales bajo presión")

    # SPY sube pero HYG baja (institucionales reduciendo riesgo)
    if spy_change_5d and spy_change_5d > 1.0 and hyg_chg and hyg_chg < -0.3:
        divergences.append("SPY+HYG-: institucionales reducen riesgo")

    # TLT sube con SPY cayendo = flight to safety
    if spy_change_5d and spy_change_5d < -1.0 and tlt_bullish:
        divergences.append("SPY-+TLT+: flight to safety confirmado")

    # Score compuesto
    score = 0.5
    if hyg_bullish:  score += 0.20   # risk-on es bullish
    if qqq_leading:  score += 0.15   # Nasdaq lidera = estructura bullish
    if not tlt_bullish: score += 0.10 # bonos no en flight-to-safety
    if dxy_bullish:  score -= 0.15   # dólar fuerte presiona SPY
    if tlt_bullish and spy_change_5d and spy_change_5d > 0:
        score -= 0.10  # divergencia bearish
    score = max(0.0, min(1.0, score))

    if divergences:
        for d in divergences:
            logger.warning(f"Divergencia cross-asset: {d}")
    logger.info(f"Cross-assets: DXY={'↑' if dxy_bullish else '↓'} TLT={'↑' if tlt_bullish else '↓'} "
                f"HYG={'↑' if hyg_bullish else '↓'} QQQ_líder={qqq_leading} | score={score:.2f}")

    return CrossAssetData(
        assets=assets,
        dxy_bullish=dxy_bullish,
        tlt_bullish=tlt_bullish,
        hyg_bullish=hyg_bullish,
        qqq_leading=qqq_leading,
        divergences=divergences,
        score=score,
    )
