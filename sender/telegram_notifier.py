import logging

import requests

import config

logger = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"


def _send(text: str) -> None:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            _API.format(token=config.TELEGRAM_BOT_TOKEN),
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=8,
        )
    except Exception as e:
        logger.warning(f"Telegram: no se pudo enviar alerta — {e}")


def signal_sent(symbol: str, action: str, confidence: float, size: float,
                trail_pct: float | None = None, vix_regime: str = "") -> None:
    mode  = "[DRY RUN] " if config.DRY_RUN else ""
    trail = f" | trail={trail_pct}%" if trail_pct else ""
    vix   = f" | VIX={vix_regime}" if vix_regime else ""
    _send(
        f"*agente01* {mode}✅ Swing entrada\n"
        f"`{action.upper()} {symbol}` | conf={confidence:.2f} | size={size}{trail}{vix}"
    )


def signal_rejected(symbol: str, action: str, reason: str) -> None:
    _send(
        f"*agente01* ⚠️ Señal rechazada por bot1\n"
        f"`{action.upper()} {symbol}`\n"
        f"Razon: {reason}"
    )


def webhook_failed(symbol: str, error: str) -> None:
    _send(
        f"*agente01* ❌ Webhook fallido — guardado como pendiente\n"
        f"Simbolo: `{symbol}`\n"
        f"Error: {error}"
    )


def no_signal_cycle(summary: str) -> None:
    _send(f"*agente01* 🔍 Ciclo sin señales\n{summary}")


def position_closed(symbol: str, reason: str) -> None:
    _send(
        f"*agente01* 🚪 Cierre forzado de posicion\n"
        f"`{symbol}`\n"
        f"Trigger: `{reason}`"
    )
