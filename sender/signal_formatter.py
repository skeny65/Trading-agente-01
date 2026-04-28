from datetime import datetime, timezone

import config
from analysis.decision_engine import EvaluationResult


def build_payload(result: EvaluationResult, all_scores: dict | None = None) -> dict:
    """Construye el payload compatible con el /webhook de bot1."""
    now = datetime.now(timezone.utc).isoformat()

    if result.action == "none":
        reason = result.reason
        if all_scores:
            scores_str = " | ".join(f"{s}:{v:.2f}" for s, v in all_scores.items())
            reason = f"{reason} [{scores_str}]"
        return {
            "timestamp": now,
            "status": "no_signal",
            "processed": False,
            "reason": reason,
            "signal": None,
        }

    return {
        "timestamp": now,
        "status": "pending",
        "processed": False,
        "signal": {
            "strategy_id": "bot2_macro_research",
            "symbol": result.symbol,
            "action": result.action,
            "confidence": result.confidence,
            "size": result.size,
            "params": {
                "source": "bot2",
                "stop_loss": config.DEFAULT_STOP_LOSS,
                "take_profit": config.DEFAULT_TAKE_PROFIT,
                "research_summary": result.reason,
                "score_breakdown": {
                    "sentiment": round(result.score.sentiment * 0.30, 3),
                    "trend":     round(result.score.trend     * 0.30, 3),
                    "macro":     round(result.score.macro     * 0.25, 3),
                    "news":      round(result.score.vix       * 0.15, 3),
                },
            },
        },
    }
