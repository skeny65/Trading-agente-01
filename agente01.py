"""
agente01 — Agente de investigacion financiera autonomo.
Estrategia: Swing Trading con Trailing Stop Dinamico calibrado por regimen VIX.

Ciclo cada 60 minutos (horario de mercado). Investigacion multifuente -> scoring ->
decision -> señal a bot1 via webhook. El agente no ejecuta ordenes directamente.

Cada resultado (APPROVE, NO_SIGNAL, HOLDING, COOLDOWN, EXIT) se guarda en:
  - state/decision_log.jsonl  (una linea JSON por evento)
  - logs/<cycle_id>.json      (reporte completo del ciclo)
  - logs/trade_log.xlsx       (una fila por simbolo por ciclo)
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
from analysis import decision_engine, exit_evaluator, opportunity_scorer, sentiment_analyzer
from excel_logger import append_excel_rows
from research import macro_indicators, market_data, news_fetcher
from sender import signal_formatter, telegram_notifier, webhook_client

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("agente01")

# ── Rutas ─────────────────────────────────────────────────────────────────────
STATE_DIR           = Path(__file__).parent / "state"
LOGS_DIR            = Path(__file__).parent / "logs"
SIGNALS_FILE        = STATE_DIR / "last_signals.json"
LOG_FILE            = STATE_DIR / "decision_log.jsonl"
OPEN_POSITIONS_FILE = STATE_DIR / "open_positions.json"

# Ciclos prioritarios ET: post-apertura, media sesion, pre-cierre
_PRIORITY_CYCLES = [(9, 45), (12, 30), (15, 30)]


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


# ── Posiciones abiertas ───────────────────────────────────────────────────────
def _load_open_positions() -> dict:
    try:
        return json.loads(OPEN_POSITIONS_FILE.read_text())
    except Exception:
        return {}


def _save_open_positions(data: dict) -> None:
    OPEN_POSITIONS_FILE.write_text(json.dumps(data, indent=2))


def _add_open_position(symbol: str, vix_regime: str, trail_config: dict, result) -> None:
    positions = _load_open_positions()
    positions[symbol] = {
        "opened_at":           datetime.now(timezone.utc).isoformat(),
        "vix_regime_at_entry": vix_regime,
        "max_holding_days":    trail_config["max_holding_days"],
        "action":              result.action,
        "confidence":          result.confidence,
        "size":                result.size,
    }
    _save_open_positions(positions)


def _remove_open_position(symbol: str) -> None:
    positions = _load_open_positions()
    positions.pop(symbol, None)
    _save_open_positions(positions)


# ── Log de decisiones (JSONL) ─────────────────────────────────────────────────
def _log_decision(entry: dict) -> None:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Reporte de ciclo ──────────────────────────────────────────────────────────
def _write_cycle_report(report: dict) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    cycle_id = report["cycle_id"]
    path     = LOGS_DIR / f"{cycle_id}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Reporte guardado -> logs/{cycle_id}.json")


# ── Ciclos prioritarios ───────────────────────────────────────────────────────
def _is_priority_cycle() -> bool:
    tz  = pytz.timezone(config.MARKET_TZ)
    now = datetime.now(tz)
    for hour, minute in _PRIORITY_CYCLES:
        if now.hour == hour and abs(now.minute - minute) <= 5:
            return True
    return False


# ── Horario de mercado ────────────────────────────────────────────────────────
def _is_market_hours() -> bool:
    tz         = pytz.timezone(config.MARKET_TZ)
    now        = datetime.now(tz)
    if now.weekday() >= 5:
        return False
    open_time  = now.replace(hour=config.MARKET_OPEN_HOUR,  minute=config.MARKET_OPEN_MINUTE, second=0)
    close_time = now.replace(hour=config.MARKET_CLOSE_HOUR, minute=0, second=0)
    return open_time <= now <= close_time


# ── Constructor de filas Excel ────────────────────────────────────────────────
def _excel_row(
    cycle_meta: dict,
    symbol: str,
    status: str,
    decision: str,
    action: str = "",
    quote=None,
    sentiment=None,
    macro=None,
    score=None,
    trail_config: dict | None = None,
    confidence: float = 0.0,
    size: float = 0.0,
    reason: str = "",
    webhook_status: str = "n/a",
) -> dict:
    row: dict = {
        "timestamp_utc":  cycle_meta["timestamp_utc"],
        "cycle_id":       cycle_meta["cycle_id"],
        "mode":           cycle_meta["mode"],
        "priority_cycle": cycle_meta["priority_cycle"],
        "symbol":         symbol,
        "status":         status,
        "decision":       decision,
        "action":         action,
        "confidence":     confidence,
        "size":           size,
        "reason":         reason,
        "webhook_status": webhook_status,
    }
    if quote is not None:
        row.update({
            "price":          quote.price,
            "change_pct":     quote.change_pct,
            "sma20":          quote.sma20,
            "sma50":          quote.sma50,
            "trend_strength": quote.trend_strength,
            "volume_ratio":   quote.volume_ratio,
        })
    if sentiment is not None:
        row.update({
            "sentiment_compound": sentiment.compound,
            "sentiment_label":    sentiment.label,
        })
    if macro is not None:
        row.update({
            "fear_greed_score": macro.fear_greed_score,
            "fear_greed_label": macro.fear_greed_label,
            "vix":              macro.vix,
            "vix_regime":       macro.vix_regime,
        })
    if score is not None:
        row.update({
            "score_trend":     score.trend,
            "score_sentiment": score.sentiment,
            "score_macro":     score.macro,
            "score_vix":       score.vix,
            "score_total":     score.total,
        })
    if trail_config is not None:
        row.update({
            "trail_percent":    trail_config["trail_percent"],
            "take_profit_pct":  trail_config["take_profit_pct"],
            "max_holding_days": trail_config["max_holding_days"],
        })
    return row


# ── Ciclo principal ───────────────────────────────────────────────────────────
def run_cycle() -> None:
    started_at  = datetime.now(timezone.utc)
    cycle_id    = started_at.strftime("%Y-%m-%d_%H-%M-%S")
    t0          = time.monotonic()
    is_priority = _is_priority_cycle()
    prefix      = "[PRIORITY] " if is_priority else ""
    now_str     = started_at.isoformat()

    logger.info("=" * 60)
    logger.info(f"{prefix}INICIO DE CICLO | id={cycle_id}")

    cycle_meta = {
        "timestamp_utc":  now_str,
        "cycle_id":       cycle_id,
        "mode":           "DRY_RUN" if config.DRY_RUN else "LIVE",
        "priority_cycle": is_priority,
    }

    report: dict = {
        "cycle_id":         cycle_id,
        "started_at":       now_str,
        "finished_at":      None,
        "duration_seconds": None,
        "mode":             cycle_meta["mode"],
        "priority_cycle":   is_priority,
        "market_open":      False,
        "macro":            None,
        "symbols":          {},
        "summary": {
            "approved":         [],
            "exits":            [],
            "no_signal":        [],
            "cooldown":         [],
            "holding":          [],
            "no_data":          [],
            "webhook_failed":   [],
            "rejected_by_bot1": [],
        },
    }

    excel_rows: list[dict] = []

    if not _is_market_hours():
        logger.info("Mercado cerrado - ciclo omitido")
        report["finished_at"]      = datetime.now(timezone.utc).isoformat()
        report["duration_seconds"] = round(time.monotonic() - t0, 2)
        _write_cycle_report(report)
        return

    report["market_open"] = True
    webhook_client.retry_pending()

    last_signals   = _load_last_signals()
    open_positions = _load_open_positions()

    # ── 1. Macro (una vez por ciclo) ──────────────────────────────────────────
    macro = macro_indicators.get_macro_context()
    report["macro"] = {
        "fear_greed_score": macro.fear_greed_score,
        "fear_greed_label": macro.fear_greed_label,
        "vix":              macro.vix,
        "vix_regime":       macro.vix_regime,
        "macro_bias":       macro.macro_bias,
        "fetched_at":       macro.fetched_at,
    }

    # ── 2. Precios: watchlist + posiciones abiertas ───────────────────────────
    symbols_to_fetch = list(set(config.WATCHLIST) | set(open_positions.keys()))
    quotes           = market_data.get_quotes(symbols_to_fetch)
    no_signal_scores: dict[str, float] = {}

    # ── 3. Evaluacion de salidas (posiciones abiertas) ────────────────────────
    closed_this_cycle: set[str] = set()

    for symbol, position in list(open_positions.items()):
        if symbol not in quotes:
            logger.warning(f"[EXIT CHECK] {symbol}: sin datos de precio - saltando")
            _log_decision({"ts": now_str, "symbol": symbol, "decision": "EXIT_NO_DATA"})
            excel_rows.append(_excel_row(
                cycle_meta, symbol,
                status="EXIT_NO_DATA", decision="EXIT_NO_DATA", action="none",
                macro=macro, reason="Sin datos de precio para evaluar salida",
            ))
            continue

        quote     = quotes[symbol]
        headlines = news_fetcher.fetch(symbol)
        sentiment = sentiment_analyzer.analyze(headlines)
        exit_sig  = exit_evaluator.evaluate_exit(symbol, quote, sentiment, macro, position)

        if exit_sig.should_close:
            close_payload = signal_formatter.build_close_payload(symbol, exit_sig.reason)
            response      = webhook_client.send(close_payload)

            if isinstance(response, dict) and response.get("status") not in ("failed", "error"):
                _remove_open_position(symbol)
                closed_this_cycle.add(symbol)
                telegram_notifier.position_closed(symbol, exit_sig.reason)
                report["summary"]["exits"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "EXIT_FORCED",
                    "close_reason": exit_sig.reason,
                    "webhook_response": response,
                })
                excel_rows.append(_excel_row(
                    cycle_meta, symbol,
                    status="EXIT_FORCED", decision="EXIT_FORCED", action="close",
                    quote=quote, sentiment=sentiment, macro=macro,
                    reason=exit_sig.reason, webhook_status="sent",
                ))
            else:
                logger.error(f"[EXIT] {symbol}: fallo al enviar cierre - {response}")
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "EXIT_FORCED",
                    "close_reason": exit_sig.reason,
                    "webhook_response": response,
                    "error": "webhook_failed",
                })
                excel_rows.append(_excel_row(
                    cycle_meta, symbol,
                    status="EXIT_FORCED", decision="EXIT_FORCED", action="close",
                    quote=quote, sentiment=sentiment, macro=macro,
                    reason=exit_sig.reason, webhook_status="failed",
                ))
        else:
            _log_decision({
                "ts": now_str, "symbol": symbol,
                "decision": "EXIT_CHECK_OK",
                "reason": "Tesis valida — no se cierra",
            })
            excel_rows.append(_excel_row(
                cycle_meta, symbol,
                status="HOLDING_OK", decision="EXIT_CHECK_OK", action="none",
                quote=quote, sentiment=sentiment, macro=macro,
                reason="Tesis valida — no se cierra",
            ))

    # Recargar posiciones tras cierres
    open_positions = _load_open_positions()

    # ── 4. Analisis por simbolo (nuevas entradas) ─────────────────────────────
    for symbol in config.WATCHLIST:
        logger.info(f"-- Analizando {symbol} --")
        sym_report: dict = {"status": None}

        # Ya tiene posicion abierta -> no abrir otra
        if symbol in open_positions:
            logger.info(f"{symbol}: posicion abierta - esperando cierre")
            sym_report["status"]   = "HOLDING"
            sym_report["position"] = open_positions[symbol]
            report["symbols"][symbol] = sym_report
            report["summary"]["holding"].append(symbol)
            _log_decision({
                "ts": now_str, "symbol": symbol,
                "decision": "HOLDING",
                "position": open_positions[symbol],
            })
            excel_rows.append(_excel_row(
                cycle_meta, symbol,
                status="HOLDING", decision="HOLDING", action="none",
                macro=macro, reason="Posicion abierta — esperando cierre",
            ))
            continue

        if symbol not in quotes:
            logger.warning(f"{symbol}: sin datos de mercado - saltando")
            sym_report["status"] = "NO_DATA"
            report["symbols"][symbol] = sym_report
            report["summary"]["no_data"].append(symbol)
            _log_decision({"ts": now_str, "symbol": symbol, "decision": "NO_DATA"})
            excel_rows.append(_excel_row(
                cycle_meta, symbol,
                status="NO_DATA", decision="NO_DATA", action="none",
                macro=macro, reason="Sin datos de mercado",
            ))
            continue

        if _is_on_cooldown(symbol, last_signals):
            logger.info(f"{symbol}: en cooldown ({config.COOLDOWN_HOURS}h) - saltando")
            sym_report["status"] = "COOLDOWN"
            report["symbols"][symbol] = sym_report
            report["summary"]["cooldown"].append(symbol)
            _log_decision({
                "ts": now_str, "symbol": symbol,
                "decision": "COOLDOWN",
                "cooldown_hours": config.COOLDOWN_HOURS,
            })
            excel_rows.append(_excel_row(
                cycle_meta, symbol,
                status="COOLDOWN", decision="COOLDOWN", action="none",
                macro=macro, reason=f"Cooldown activo ({config.COOLDOWN_HOURS}h)",
            ))
            continue

        # Investigacion completa
        quote     = quotes[symbol]
        headlines = news_fetcher.fetch(symbol)
        sentiment = sentiment_analyzer.analyze(headlines)
        score     = opportunity_scorer.calculate(quote, sentiment, macro)
        result    = decision_engine.evaluate(symbol, quote, sentiment, macro, score)

        # Relleno del reporte JSON
        sym_report["status"] = "ANALYZED"
        sym_report["quote"] = {
            "price":          quote.price,
            "prev_close":     quote.prev_close,
            "change_pct":     quote.change_pct,
            "volume":         quote.volume,
            "avg_volume":     quote.avg_volume,
            "volume_ratio":   quote.volume_ratio,
            "sma20":          quote.sma20,
            "sma50":          quote.sma50,
            "price_vs_sma20": quote.price_vs_sma20,
            "trend":          quote.trend,
            "trend_strength": quote.trend_strength,
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
        sym_report["score"]    = dataclasses.asdict(score)
        sym_report["decision"] = {
            "verdict":    result.decision.value,
            "action":     result.action,
            "confidence": result.confidence,
            "size":       result.size,
            "reason":     result.reason,
        }
        sym_report["webhook_response"] = None

        # ── Envio ─────────────────────────────────────────────────────────────
        if result.decision.value == "APPROVE":
            trail_config = signal_formatter.get_trail_config(macro.vix_regime)
            payload      = signal_formatter.build_payload(result, macro.vix_regime)
            response     = webhook_client.send(payload)
            sym_report["trail_config"]     = trail_config
            sym_report["webhook_response"] = response

            if isinstance(response, dict) and response.get("status") == "rejected":
                reject_reason = response.get("reason", "sin razon")
                telegram_notifier.signal_rejected(symbol, result.action, reject_reason)
                report["summary"]["rejected_by_bot1"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "REJECTED_BY_BOT1",
                    "action": result.action, "reason": reject_reason,
                    "score": result.confidence,
                })
                excel_rows.append(_excel_row(
                    cycle_meta, symbol,
                    status="ANALYZED", decision="APPROVE", action=result.action,
                    quote=quote, sentiment=sentiment, macro=macro, score=score,
                    trail_config=trail_config,
                    confidence=result.confidence, size=result.size,
                    reason=result.reason, webhook_status="rejected",
                ))

            elif isinstance(response, dict) and response.get("status") == "failed":
                telegram_notifier.webhook_failed(symbol, response.get("error", ""))
                report["summary"]["webhook_failed"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "WEBHOOK_FAILED",
                    "action": result.action, "error": response.get("error"),
                    "score": result.confidence,
                })
                excel_rows.append(_excel_row(
                    cycle_meta, symbol,
                    status="ANALYZED", decision="APPROVE", action=result.action,
                    quote=quote, sentiment=sentiment, macro=macro, score=score,
                    trail_config=trail_config,
                    confidence=result.confidence, size=result.size,
                    reason=result.reason, webhook_status="failed",
                ))

            else:
                wh_status = "dry_run" if config.DRY_RUN else "sent"
                _mark_signal_sent(symbol, last_signals)
                _add_open_position(symbol, macro.vix_regime, trail_config, result)
                telegram_notifier.signal_sent(
                    symbol, result.action, result.confidence, result.size,
                    trail_pct=trail_config["trail_percent"], vix_regime=macro.vix_regime,
                )
                report["summary"]["approved"].append(symbol)
                _log_decision({
                    "ts": now_str, "symbol": symbol,
                    "decision": "APPROVE",
                    "action": result.action,
                    "confidence": result.confidence,
                    "size": result.size,
                    "reason": result.reason,
                    "trail_config": trail_config,
                    "vix_regime": macro.vix_regime,
                    "webhook_response": response,
                    "dry_run": config.DRY_RUN,
                })
                excel_rows.append(_excel_row(
                    cycle_meta, symbol,
                    status="ANALYZED", decision="APPROVE", action=result.action,
                    quote=quote, sentiment=sentiment, macro=macro, score=score,
                    trail_config=trail_config,
                    confidence=result.confidence, size=result.size,
                    reason=result.reason, webhook_status=wh_status,
                ))

        else:
            no_signal_scores[symbol] = result.score.total
            report["summary"]["no_signal"].append(symbol)
            logger.info(f"{symbol}: {result.decision.value} - {result.reason}")
            _log_decision({
                "ts": now_str, "symbol": symbol,
                "decision": result.decision.value,
                "reason": result.reason,
                "score": result.score.total,
            })
            excel_rows.append(_excel_row(
                cycle_meta, symbol,
                status="ANALYZED", decision="NO_SIGNAL", action="none",
                quote=quote, sentiment=sentiment, macro=macro, score=score,
                confidence=result.confidence, size=0.0,
                reason=result.reason, webhook_status="n/a",
            ))

        report["symbols"][symbol] = sym_report

    # ── 5. Ciclo sin senales -> informar a bot1 ───────────────────────────────
    if no_signal_scores and not report["summary"]["approved"]:
        scores_str = " | ".join(f"{s}:{v:.2f}" for s, v in no_signal_scores.items())
        summary    = f"Ningun simbolo supera umbral {config.MIN_CONFIDENCE} [{scores_str}]"
        logger.info(f"Ciclo sin senales - {summary}")
        webhook_client.send(signal_formatter.build_no_signal_payload(summary))
        telegram_notifier.no_signal_cycle(summary)

    # ── 6. Persistir resultados ───────────────────────────────────────────────
    report["finished_at"]      = datetime.now(timezone.utc).isoformat()
    report["duration_seconds"] = round(time.monotonic() - t0, 2)
    _write_cycle_report(report)

    # Guardar en Excel (todas las filas del ciclo de una vez)
    append_excel_rows(excel_rows)

    logger.info(
        f"{prefix}FIN DE CICLO | {report['duration_seconds']}s "
        f"| aprobados={report['summary']['approved']} "
        f"| salidas={report['summary']['exits']} "
        f"| holding={report['summary']['holding']}"
    )
    logger.info("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        config.validate()
    except EnvironmentError as e:
        logger.error(f"Configuracion invalida: {e}")
        sys.exit(1)

    mode = "DRY RUN" if config.DRY_RUN else "LIVE"
    logger.info(f"agente01 iniciado | modo={mode} | watchlist={config.WATCHLIST}")
    logger.info(
        f"Ciclo cada {config.CYCLE_INTERVAL_MINUTES}min | "
        f"umbral={config.MIN_CONFIDENCE} | consenso={config.CONSENSUS_REQUIRED}/3 | "
        f"cooldown={config.COOLDOWN_HOURS}h"
    )

    run_cycle()

    scheduler = BlockingScheduler(timezone=config.MARKET_TZ)
    scheduler.add_job(
        run_cycle,
        trigger="interval",
        minutes=config.CYCLE_INTERVAL_MINUTES,
        id="research_cycle",
    )

    logger.info(f"Scheduler activo - proximo ciclo en {config.CYCLE_INTERVAL_MINUTES}min")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("agente01 detenido manualmente")
