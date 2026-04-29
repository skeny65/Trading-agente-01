"""
Análisis técnico multi-timeframe: 1D (diario), 4H (4 horas), 1H (1 hora).
Un trader profesional confirma la dirección en los 3 timeframes antes de entrar.
"""
import logging
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

import config
from research.technical.indicators import get_indicators_snapshot
from research.technical.key_levels import KeyLevels, get_key_levels

logger = logging.getLogger(__name__)


@dataclass
class TimeframeSignal:
    timeframe: str          # "1D" | "4H" | "1H"
    trend: str              # "bullish" | "bearish" | "neutral"
    rsi: float | None
    macd_bullish: bool
    above_sma200: bool | None
    above_sma50: bool | None
    above_sma20: bool | None
    vol_ratio: float | None
    score: float            # 0.0–1.0


@dataclass
class MultiTimeframeAnalysis:
    daily:    TimeframeSignal
    four_h:   TimeframeSignal
    one_h:    TimeframeSignal
    key_levels: KeyLevels
    alignment: str          # "bullish" | "bearish" | "mixed"
    bullish_count: int      # cuántos timeframes son bullish (0–3)
    rsi_veto: bool          # True si RSI diario > 75 (sobrecompra)
    sma200_veto: bool       # True si precio < SMA200 diario
    atr_veto: bool          # True si ATR anómalo > 2x su media 30d
    overall_score: float    # 0.0–1.0


def _classify_trend(ind: dict) -> str:
    close  = ind.get("close")
    sma20  = ind.get("sma20")
    sma50  = ind.get("sma50")
    if close is None or sma20 is None:
        return "neutral"
    if close > sma20 and (sma50 is None or sma20 > sma50):
        return "bullish"
    if close < sma20 and (sma50 is None or sma20 < sma50):
        return "bearish"
    return "neutral"


def _score_timeframe(ind: dict) -> float:
    score = 0.5
    close  = ind.get("close")
    sma20  = ind.get("sma20")
    sma50  = ind.get("sma50")
    sma200 = ind.get("sma200")
    rsi    = ind.get("rsi14")
    macd_d = ind.get("macd_diff")

    if close and sma20:
        score += 0.15 if close > sma20 else -0.15
    if close and sma50:
        score += 0.10 if close > sma50 else -0.10
    if close and sma200:
        score += 0.10 if close > sma200 else -0.10
    if rsi is not None:
        if 45 <= rsi <= 65:
            score += 0.10
        elif rsi > 75 or rsi < 25:
            score -= 0.15
    if macd_d is not None:
        score += 0.10 if macd_d > 0 else -0.10

    return max(0.0, min(1.0, score))


def _analyze_timeframe(df: pd.DataFrame, label: str) -> TimeframeSignal:
    ind   = get_indicators_snapshot(df)
    trend = _classify_trend(ind)
    score = _score_timeframe(ind)

    rsi        = ind.get("rsi14")
    macd_diff  = ind.get("macd_diff")
    close      = ind.get("close")
    sma200     = ind.get("sma200")
    sma50      = ind.get("sma50")
    sma20      = ind.get("sma20")
    vol_ratio  = ind.get("vol_ratio")

    return TimeframeSignal(
        timeframe=label,
        trend=trend,
        rsi=rsi,
        macd_bullish=bool(macd_diff and macd_diff > 0),
        above_sma200=bool(close > sma200) if close and sma200 else None,
        above_sma50=bool(close > sma50) if close and sma50 else None,
        above_sma20=bool(close > sma20) if close and sma20 else None,
        vol_ratio=vol_ratio,
        score=score,
    )


def _check_atr_anomaly(df_daily: pd.DataFrame) -> bool:
    """True si ATR actual > 2× su media de los últimos 30 días."""
    try:
        from research.technical.indicators import add_indicators
        df = add_indicators(df_daily)
        atr_series = df["atr14"].dropna()
        if len(atr_series) < 31:
            return False
        current_atr = float(atr_series.iloc[-1])
        avg_atr_30d = float(atr_series.iloc[-31:-1].mean())
        return current_atr > 2 * avg_atr_30d
    except Exception:
        return False


def get_multi_timeframe_analysis(symbol: str = None) -> MultiTimeframeAnalysis:
    """
    Descarga datos en 3 timeframes y analiza la alineación técnica.
    Fallback: devuelve señal neutral si yfinance falla.
    """
    sym = symbol or config.SYMBOL

    try:
        ticker = yf.Ticker(sym)

        # Diario: 1 año para SMA200 y key levels
        df_daily = ticker.history(period="1y", interval="1d")
        # 4H: aproximamos resampling desde datos horarios de 60 días
        df_1h_raw = ticker.history(period="60d", interval="1h")
        df_4h = df_1h_raw.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min",
            "Close": "last", "Volume": "sum",
        }).dropna()
        # 1H: 30 días a resolución horaria
        df_1h = ticker.history(period="30d", interval="1h")

        if df_daily.empty or df_1h.empty:
            raise ValueError("yfinance retornó DataFrames vacíos")

    except Exception as exc:
        logger.warning(f"MultiTimeframe fetch error ({sym}): {exc}")
        neutral = TimeframeSignal(
            timeframe="?", trend="neutral", rsi=50.0,
            macd_bullish=False, above_sma200=None,
            above_sma50=None, above_sma20=None,
            vol_ratio=1.0, score=0.5,
        )
        from research.technical.key_levels import KeyLevels
        return MultiTimeframeAnalysis(
            daily=neutral, four_h=neutral, one_h=neutral,
            key_levels=KeyLevels(None,None,None,None,None,None,None,None,None),
            alignment="mixed", bullish_count=0,
            rsi_veto=False, sma200_veto=False, atr_veto=False,
            overall_score=0.5,
        )

    daily_tf = _analyze_timeframe(df_daily, "1D")
    four_h_tf = _analyze_timeframe(df_4h, "4H") if not df_4h.empty else daily_tf
    one_h_tf  = _analyze_timeframe(df_1h, "1H")
    levels    = get_key_levels(df_daily)

    # Contar timeframes bullish
    bullish_count = sum([
        daily_tf.trend == "bullish",
        four_h_tf.trend == "bullish",
        one_h_tf.trend == "bullish",
    ])

    alignment = "bullish" if bullish_count >= 2 else ("bearish" if bullish_count == 0 else "mixed")

    # Vetos técnicos
    rsi_veto    = bool(daily_tf.rsi and daily_tf.rsi > 75)
    sma200_veto = daily_tf.above_sma200 is False
    atr_veto    = _check_atr_anomaly(df_daily)

    # Score compuesto (pesos: diario 50%, 4H 30%, 1H 20%)
    base_score = (daily_tf.score * 0.50 + four_h_tf.score * 0.30 + one_h_tf.score * 0.20)
    overall_score = 0.0 if (rsi_veto or sma200_veto) else base_score

    logger.info(
        f"Técnico [{sym}]: 1D={daily_tf.trend} 4H={four_h_tf.trend} 1H={one_h_tf.trend} "
        f"| alineación={alignment} ({bullish_count}/3) | score={overall_score:.2f}"
        + (" [RSI_VETO]" if rsi_veto else "")
        + (" [SMA200_VETO]" if sma200_veto else "")
        + (" [ATR_VETO]" if atr_veto else "")
    )

    return MultiTimeframeAnalysis(
        daily=daily_tf,
        four_h=four_h_tf,
        one_h=one_h_tf,
        key_levels=levels,
        alignment=alignment,
        bullish_count=bullish_count,
        rsi_veto=rsi_veto,
        sma200_veto=sma200_veto,
        atr_veto=atr_veto,
        overall_score=overall_score,
    )
