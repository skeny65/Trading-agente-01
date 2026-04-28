import json
import logging
import time
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_PENDING_FILE = Path(__file__).parent.parent / "state" / "pending_signals.json"


def _load_pending() -> list[dict]:
    try:
        return json.loads(_PENDING_FILE.read_text())
    except Exception:
        return []


def _save_pending(signals: list[dict]) -> None:
    _PENDING_FILE.write_text(json.dumps(signals, indent=2))


def _save_to_pending(payload: dict) -> None:
    signals = _load_pending()
    signals.append(payload)
    _save_pending(signals)
    logger.info(f"Señal guardada como pendiente (total pendientes: {len(signals)})")


def _post(payload: dict, headers: dict) -> dict:
    """Intenta enviar con backoff exponencial. Retorna el resultado."""
    last_error = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = requests.post(
                config.WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            response = r.json()
            logger.info(f"Webhook OK (intento {attempt}): {response}")
            return response

        except requests.exceptions.ConnectionError as e:
            last_error = str(e)
            logger.warning(f"Intento {attempt}/{_MAX_RETRIES} — bot1 no disponible")
        except requests.exceptions.Timeout:
            last_error = "timeout"
            logger.warning(f"Intento {attempt}/{_MAX_RETRIES} — timeout")
        except requests.exceptions.HTTPError:
            # 4xx: error del payload, no tiene sentido reintentar
            logger.error(f"HTTP {r.status_code} de bot1: {r.text}")
            return {"status": "error", "http_code": r.status_code, "detail": r.text}
        except Exception as e:
            last_error = str(e)
            logger.error(f"Error inesperado: {e}")

        if attempt < _MAX_RETRIES:
            delay = 5 * attempt  # backoff: 5s, 10s, 15s
            time.sleep(delay)

    return {"status": "failed", "error": last_error}


def send(payload: dict) -> dict:
    """Envía el payload a bot1. Maneja dry_run, rejected y fallos."""
    if config.DRY_RUN:
        symbol = (payload.get("signal") or {}).get("symbol", "?")
        action = (payload.get("signal") or {}).get("action", "?")
        logger.info(f"[DRY_RUN] Webhook NO enviado — {action.upper()} {symbol}")
        return {"status": "dry_run"}

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": config.WEBHOOK_SECRET,
    }

    response = _post(payload, headers)

    # Flujo D: bot1 rechazó la señal (bot pausado por el manager)
    if isinstance(response, dict) and response.get("status") == "rejected":
        reason = response.get("reason", "sin razón")
        logger.warning(f"bot1 rechazó la señal: {reason}")
        return response

    # no_signal confirmado por bot1 — respuesta informativa, no es fallo
    if isinstance(response, dict) and response.get("status") == "received_no_signal":
        logger.info("bot1 confirmo recepcion de no_signal")
        return response

    # Flujo C: fallo de red — guardar para reintentar (solo para pending, no no_signal)
    if isinstance(response, dict) and response.get("status") == "failed":
        if payload.get("status") == "pending":
            _save_to_pending(payload)

    return response


def retry_pending() -> int:
    """Intenta reenviar señales pendientes. Retorna cuántas se enviaron con éxito."""
    signals = _load_pending()
    if not signals:
        return 0

    logger.info(f"Reintentando {len(signals)} señal(es) pendiente(s)...")
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Secret": config.WEBHOOK_SECRET,
    }

    remaining = []
    sent_count = 0
    for payload in signals:
        response = _post(payload, headers)
        if isinstance(response, dict) and response.get("status") not in ("failed", "error"):
            sent_count += 1
        else:
            remaining.append(payload)

    _save_pending(remaining)
    if sent_count:
        logger.info(f"{sent_count} señal(es) pendiente(s) enviada(s) OK")
    return sent_count
