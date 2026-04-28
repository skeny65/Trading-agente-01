"""
agente01 — Agente de investigación financiera autónomo.
Investiga internet, puntúa oportunidades y envía señales a bot1 vía webhook.
"""
import dataclasses
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler

import config
from analysis import decision_engine, opportunity_scorer, sentiment_analyzer
from research import macro_indicators, market_data, news_fetcher
from sender import signal_formatter, telegram_notifier, webhook_client

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("agente01")

# ── Rutas ─────────────────────────────────────────────────────────────────────
STATE_DIR    = Path(__file__).parent / "state"
LOGS_DIR     = Path(__file__).parent / "logs"
SIGNALS_FILE = STATE_DIR / "last_signals.json"
LOG_FILE     = STATE_DIR / "decision_log.jsonl"


# ── Cooldown ──────────────────────────────────────────────────────────────────
def _load_last_signals() -> dict:
    try:
        return json.loads(SIGNALS_FILE.read_text())
    except Exception:
        return {}


def _save_last_signals(data: dict) -> None:
    SIGNALS_FILE.write_text(json.dumps(data, indent=2))


def _is_on_cooldown(symbol: str, last_signals: dict) -> bool:
    ts_str = last_signals.get(symbol)
    if not ts_str:
        return False
    last = datetime.fromisoformat(ts_str)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600
    return elapsed_hours < config.COOLDOWN_HOURS


def _mark_signal_sent(symbol: str, last_signals: dict) -> None:
    last_signals[symbol] = datetime.now(timezone.utc).isoformat()
    _save_last_signals(last_signals)


# ── Log de decisiones (append) ────────────────────────────────────────────────
def _log_decision(entry: dict) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Reporte de ciclo completo ─────────────────────────────────────────────────
def _write_cycle_report(report: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    cycle_id = report["cycle_id"]
    path = LOGS_DIR / f"{cycle_id}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Reporte del ciclo guardado -> logs/{cycle_id}.json")


# ── Horario de mercado ────────────────────────────────────────────────────────
def _is_market_hours() -> bool:
    tz = pytz.timezone(config.MARKET_TZ)
    now = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    open_time  = now.replace(hour=config.MARKET_OPEN_HOUR,  minute=config.MARKET_OPEN_MINUTE, second=0)
    close_time = now.replace(hour=config.MARKET_CLOSE_HOUR, minute=0, second=0)
    return open_time <= now <= close_time


# ── Ciclo principal ───────────────────────────────────────────────────────────
def run_cycle() -> None:
    started_at  = datetime.now(timezone.utc)
    cycle_id    = started_at.strftime("%Y-%m-%d_%H-%M-%S")
    t0          = time.monotonic()

    logger.info("=" * 60)
    logger.info(f"INICIO DE CICLO | id={cycle_id}")

    # Esqueleto del reporte — se rellena a lo largo del ciclo
    report: dict = {
        "cycle_id":        cycle_id,
        "started_at":      started_at.isoformat(),
        "finished_at":     None,
        "duration_seconds": None,
        "mode":            "DRY_RUN" if config.DRY_RUN else "LIVE",
        "market_open":     False,
        "macro":           None,
        "symbols":         {},
        "summary": {
            "approved":        [],
            "no_signal":       [],
            "cooldown":        [],
            "no_data":         [],
            "webhook_failed":  [],
            "rejected_by_bot1": [],
        },
    }

    if not _is_market_hours():
        logger.info("Mercado cerrado — ciclo omitido")
        report["market_open"] = False
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["duration_seconds"] = round(time.monotonic() - t0, 2)
        _write_cycle_report(report)
        return

    report["market_open"] = True

    # Reintentar señales pendientes
    webhook_client.retry_pending()

    last_signals = _load_last_signals()

    # ── 1. Datos macro ────────────────────────────────────────────────────────
    macro = macro_indicators.get_macro_context()
    report["macro"] = {
        "fear_greed_score": macro.fear_greed_score,
        "fear_greed_label": macro.fear_greed_label,
        "vix":              macro.vix,
        "vix_regime":       macro.vix_regime,
        "macro_bias":       macro.macro_bias,
        "fetched_at":       macro.fetched_at,
    }

    # ── 2. Datos de precio ────────────────────────────────────────────────────
    quotes   = market_data.get_quotes(config.WATCHLIST)
    now_str  = datetime.now(timezone.utc).isoformat()
    no_signal_scores: dict[str, float] = {}

    # ── 3. Por símbolo ────────────────────────────────────────────────────────
    for symbol in config.WATCHLIST:
        logger.info(f"── Analizando {symbol} ──")
        sym_report: dict = {"status": None}

        if symbol not in quotes:
            logger.warning(f"{symbol}: sin datos de mercado — saltando")
            sym_report["status"] = "NO_DATA"
            report["symbols"][symbol] = sym_report
            report["summary"]["no_data"].append(symbol)
            continue

        if _is_on_cooldown(symbol, last_signals):
            logger.info(f"{symbol}: en cooldown ({config.COOLDOWN_HOURS}h) — saltando")
            sym_report["status"] = "COOLDOWN"
            report["symbols"][symbol] = sym_report
            report["summary"]["cooldown"].append(symbol)
            continue

        # Investigación
        quote     = quotes[symbol]
        headlines = news_fetcher.fetch(symbol, hours=6)
        sentiment = sentiment_analyzer.analyze(headlines)
        score     = opportunity_scorer.calculate(quote, sentiment, macro)
        result    = decision_engine.evaluate(symbol, quote, sentiment, macro, score)

        # Relleno del reporte por símbolo
        sym_report["status"] = "ANALYZED"
        sym_report["quote"] = {
            "price":          quote.price,
            "prev_close":     quote.prev_close,
            "change_pct":     quote.change_pct,
            "volume":         quote.volume,
            "avg_volume":     quote.avg_volume,
            "volume_ratio":   quote.volume_ratio,
            "sma20":          quote.sma20,
            "price_vs_sma20": quote.price_vs_sma20,
            "trend":          quote.trend,
        }
        sym_report["headlines_count"] = sentiment.headline_count
        sym_report["headlines"] = [
            {"title": h.title, "source": h.source, "published_at": h.published_at}
            for h in headlines
        ]
        sym_report["sentiment"] = {
            "compound":       sentiment.compound,
            "label":          sentiment.label,
            "positive_ratio": sentiment.positive_ratio,
            "negative_ratio": sentiment.negative_ratio,
        }
        sym_report["score"] = dataclasses.asdict(score)
        sym_report["decision"] = {
            "verdict":    result.decision.value,
            "action":     result.action,
            "confidence": result.confidence,
            "size":       result.size,
            "reason":     result.reason,
        }
        sym_report["webhook_response"] = None

        # ── Envío ─────────────────────────────────────────────────────────────
        if result.decision.value == "APPROVE":
            payload  = signal_formatter.build_payload(result)
            response = webhook_client.send(payload)
            sym_report["webhook_response"] = response

            if isinstance(response, dict) and response.get("status") == "rejected":
                reject_reason = response.get("reason", "sin razón")
                telegram_notifier.signal_rejected(symbol, result.action, reject_reason)
                report["summary"]["rejected_by_bot1"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "REJECTED_BY_BOT1",
                    "action": result.action, "reason": reject_reason,
                })

            elif isinstance(response, dict) and response.get("status") == "failed":
                telegram_notifier.webhook_failed(symbol, response.get("error", ""))
                report["summary"]["webhook_failed"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "WEBHOOK_FAILED",
                    "action": result.action, "error": response.get("error"),
                })

            else:
                _mark_signal_sent(symbol, last_signals)
                telegram_notifier.signal_sent(symbol, result.action, result.confidence, result.size)
                report["summary"]["approved"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "APPROVE",
                    "action": result.action,
                    "confidence": result.confidence,
                    "size": result.size,
                    "reason": result.reason,
                    "webhook_response": response,
                    "dry_run": config.DRY_RUN,
                })

        else:
            no_signal_scores[symbol] = result.score.total
            report["summary"]["no_signal"].append(symbol)
            logger.info(f"{symbol}: {result.decision.value} — {result.reason}")
            _log_decision({
                "ts": now_str, "symbol": symbol,
                "decision": result.decision.value,
                "reason": result.reason,
                "score": result.score.total,
            })

        report["symbols"][symbol] = sym_report

    # Ciclo sin señales: notificar a bot1 y a Telegram
    if no_signal_scores and not report["summary"]["approved"]:
        scores_str = " | ".join(f"{s}:{v:.2f}" for s, v in no_signal_scores.items())
        summary    = f"Ningún símbolo supera umbral {config.MIN_CONFIDENCE} [{scores_str}]"
        logger.info(f"Ciclo sin señales — {summary}")

        # Enviar no_signal a bot1 para que quede registrado en su log
        no_signal_payload = {
            "timestamp": now_str,
            "status":    "no_signal",
            "processed": False,
            "reason":    summary,
            "signal":    None,
        }
        webhook_client.send(no_signal_payload)

        telegram_notifier.no_signal_cycle(summary)

    # ── Cerrar reporte ────────────────────────────────────────────────────────
    report["finished_at"]      = datetime.now(timezone.utc).isoformat()
    report["duration_seconds"] = round(time.monotonic() - t0, 2)
    _write_cycle_report(report)

    logger.info(
        f"FIN DE CICLO | duración={report['duration_seconds']}s "
        f"| aprobados={report['summary']['approved']} "
        f"| sin_señal={report['summary']['no_signal']}"
    )
    logger.info("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        config.validate()
    except EnvironmentError as e:
        logger.error(f"Configuración inválida: {e}")
        sys.exit(1)

    mode = "DRY RUN" if config.DRY_RUN else "LIVE"
    logger.info(f"agente01 iniciado | modo={mode} | watchlist={config.WATCHLIST}")
    logger.info(f"Ciclo cada {config.CYCLE_INTERVAL_HOURS}h | umbral={config.MIN_CONFIDENCE}")

    run_cycle()

    scheduler = BlockingScheduler(timezone=config.MARKET_TZ)
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        hours=config.CYCLE_INTERVAL_HOURS,
        id="research_cycle",
    )

    logger.info(f"Scheduler activo — próximo ciclo en {config.CYCLE_INTERVAL_HOURS}h")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("agente01 detenido manualmente")
