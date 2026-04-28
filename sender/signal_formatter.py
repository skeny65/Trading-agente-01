from datetime import datetime, timezone

import config
from analysis.decision_engine import EvaluationResult


# ── Trailing config por régimen VIX ──────────────────────────────────────────

def get_trail_config(vix_regime: str) -> dict:
    """Devuelve trail_percent, take_profit_pct y max_holding_days según el VIX."""
    if vix_regime == "low":
        return {
            "trail_percent":    config.TRAIL_PERCENT_LOW_VIX,
            "take_profit_pct":  None,   # dejar correr sin TP en VIX bajo
            "max_holding_days": config.MAX_HOLDING_DAYS_LOW,
        }
    elif vix_regime == "moderate":
        return {
            "trail_percent":    config.TRAIL_PERCENT_MODERATE_VIX,
            "take_profit_pct":  None,
            "max_holding_days": config.MAX_HOLDING_DAYS_MODERATE,
        }
    elif vix_regime == "high":
        return {
            "trail_percent":    config.TRAIL_PERCENT_HIGH_VIX,
            "take_profit_pct":  config.TAKE_PROFIT_HIGH_VIX,
            "max_holding_days": config.MAX_HOLDING_DAYS_HIGH,
        }
    else:
        # extreme — el decision_engine ya bloquea nuevas posiciones,
        # pero si llegara aquí por algún motivo, usamos parámetros defensivos
        return {
            "trail_percent":    config.TRAIL_PERCENT_HIGH_VIX,
            "take_profit_pct":  config.TAKE_PROFIT_HIGH_VIX,
            "max_holding_days": config.MAX_HOLDING_DAYS_HIGH,
        }


# ── Payload de apertura (APPROVE BUY) ────────────────────────────────────────

def build_payload(result: EvaluationResult, vix_regime: str) -> dict:
    """Construye el payload de señal de compra para bot1."""
    now          = datetime.now(timezone.utc).isoformat()
    trail_config = get_trail_config(vix_regime)

    return {
        "timestamp": now,
        "status":    "pending",
        "processed": False,
        "signal": {
            "strategy_id": "bot2_swing_trailing",
            "symbol":      result.symbol,
            "action":      result.action,
            "confidence":  result.confidence,
            "size":        result.size,
            "params": {
                "source":             "bot2",
                "exit_strategy":      config.EXIT_STRATEGY,
                "trail_percent":      trail_config["trail_percent"],
                "take_profit_pct":    trail_config["take_profit_pct"],
                "max_holding_days":   trail_config["max_holding_days"],
                "vix_regime_at_entry": vix_regime,
                "research_summary":   result.reason,
                "score_breakdown": {
                    "sentiment": round(result.score.sentiment * 0.20, 3),
                    "trend":     round(result.score.trend     * 0.40, 3),
                    "macro":     round(result.score.macro     * 0.25, 3),
                    "news":      round(result.score.vix       * 0.15, 3),
                },
            },
        },
    }


# ── Payload de cierre forzado (invalidación de tesis) ────────────────────────

def build_close_payload(symbol: str, close_reason: str) -> dict:
    """Construye el payload de cierre forzado para bot1."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp": now,
        "status":    "pending",
        "processed": False,
        "signal": {
            "strategy_id": "bot2_swing_trailing",
            "symbol":      symbol,
            "action":      "close",
            "confidence":  1.0,
            "size":        1.0,
            "params": {
                "source":           "bot2",
                "close_reason":     close_reason,
                "research_summary": f"Cierre forzado: {close_reason}",
            },
        },
    }


# ── Payload informativo de ciclo sin señal ────────────────────────────────────

def build_no_signal_payload(reason: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "timestamp": now,
        "status":    "no_signal",
        "processed": False,
        "reason":    reason,
        "signal":    None,
    }
