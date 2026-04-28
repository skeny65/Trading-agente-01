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


def signal_sent(symbol: str, action: str, confidence: float, size: float) -> None:
    mode = "[DRY RUN] " if config.DRY_RUN else ""
    _send(
        f"*agente01* {mode}✅\n"
        f"Señal enviada a bot1\n"
        f"`{action.upper()} {symbol}` | conf={confidence:.2f} | size={size}"
    )


def signal_rejected(symbol: str, action: str, reason: str) -> None:
    _send(
        f"*agente01* ⚠️\n"
        f"Señal rechazada por bot1\n"
        f"`{action.upper()} {symbol}`\n"
        f"Razón: {reason}"
    )


def webhook_failed(symbol: str, error: str) -> None:
    _send(
        f"*agente01* ❌\n"
        f"Webhook falló — señal guardada como pendiente\n"
        f"Símbolo: `{symbol}`\n"
        f"Error: {error}"
    )


def no_signal_cycle(summary: str) -> None:
    _send(f"*agente01* 🔍 Ciclo sin señales\n{summary}")
