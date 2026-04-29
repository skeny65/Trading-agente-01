"""
Cálculo de indicadores técnicos usando la librería `ta`.
Recibe un DataFrame de yfinance y retorna indicadores calculados.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def _require_ta():
    try:
        import ta
        return ta
    except ImportError:
        raise ImportError("Instalar: pip install ta>=0.11.0")


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega columnas de indicadores técnicos al DataFrame.
    Columnas de entrada requeridas: Open, High, Low, Close, Volume
    """
    ta = _require_ta()
    df = df.copy()

    close  = df["Close"]
    high   = df["High"]
    low    = df["Low"]
    volume = df["Volume"]

    # Medias móviles
    df["sma9"]  = ta.trend.sma_indicator(close, window=9)
    df["sma20"] = ta.trend.sma_indicator(close, window=20)
    df["sma50"] = ta.trend.sma_indicator(close, window=50)
    df["sma200"] = ta.trend.sma_indicator(close, window=200)
    df["ema9"]  = ta.trend.ema_indicator(close, window=9)

    # RSI
    df["rsi14"] = ta.momentum.rsi(close, window=14)

    # MACD
    macd = ta.trend.MACD(close)
    df["macd"]        = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_diff"]   = macd.macd_diff()

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_pct"]   = bb.bollinger_pband()  # 0=lower, 1=upper

    # ATR (volatilidad)
    df["atr14"] = ta.volatility.average_true_range(high, low, close, window=14)

    # Volumen relativo (vs media 20 periodos)
    df["vol_ma20"]   = volume.rolling(window=20).mean()
    df["vol_ratio"]  = volume / df["vol_ma20"]

    return df


def get_indicators_snapshot(df: pd.DataFrame) -> dict:
    """
    Retorna el snapshot del último período: valores actuales de todos los indicadores.
    """
    df = add_indicators(df)
    last = df.iloc[-1]

    def safe(val):
        try:
            return None if pd.isna(val) else float(val)
        except Exception:
            return None

    return {
        "close":       safe(last["Close"]),
        "sma9":        safe(last.get("sma9")),
        "sma20":       safe(last.get("sma20")),
        "sma50":       safe(last.get("sma50")),
        "sma200":      safe(last.get("sma200")),
        "ema9":        safe(last.get("ema9")),
        "rsi14":       safe(last.get("rsi14")),
        "macd":        safe(last.get("macd")),
        "macd_signal": safe(last.get("macd_signal")),
        "macd_diff":   safe(last.get("macd_diff")),
        "bb_upper":    safe(last.get("bb_upper")),
        "bb_lower":    safe(last.get("bb_lower")),
        "bb_pct":      safe(last.get("bb_pct")),
        "atr14":       safe(last.get("atr14")),
        "vol_ratio":   safe(last.get("vol_ratio")),
    }
