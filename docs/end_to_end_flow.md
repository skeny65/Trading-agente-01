# Flujos End-to-End — agente01

agente01 tiene 5 flujos posibles en cada ciclo.

---

## Flujo A — Caso Feliz: Oportunidad Detectada y Ejecutada

```
APScheduler dispara run_cycle() — 09:45 ET [PRIORITY]
    │
    ├─ FASE 0: retry_pending() — sin señales pendientes (queue vacío)
    │
    ├─ FASE 1: EXIT EVALUATOR
    │   ├─ SPY tiene posición abierta (opened_at: ayer 14:00)
    │   │     Quote fresco: trend=bullish, vol_ratio=1.1
    │   │     Sentiment: compound=+0.3 (positivo)
    │   │     exit_evaluator.evaluate_exit()
    │   │       T1: vix=16.5 != extreme ✓ no cierra
    │   │       T2: trend != bearish ✓ no cierra
    │   │       T3: compound > -0.5 ✓ no cierra
    │   │       T4: elapsed=1d < max_holding=10d ✓ no cierra
    │   └─ ExitSignal(should_close=False) → log "EXIT_CHECK_OK" → fila Excel
    │
    ├─ FASE 2: INVESTIGACIÓN MACRO (una vez por ciclo)
    │   ├─ macro_indicators.get_macro_context()
    │   │     CNN Fear&Greed=65 (Greed)  → macro_score=0.65
    │   │     VIX=16.5 (moderate)        → vix_score=0.65
    │   │     macro_bias=bullish (F&G>=60 y VIX<20)
    │   │     trail_config: trail_percent=4.0%, tp=null, max_days=10
    │   │
    │   └─ market_data.get_quotes(["QQQ", "IWM", "DIA", "XLK", "XLF", "XLE", "XLV"])
    │         (SPY ya está en open_positions — se incluye en el fetch pero skip en análisis)
    │
    ├─ FASE 3: ANÁLISIS POR SÍMBOLO
    │   │
    │   ├─ [SPY] skip — posición abierta (HOLDING)
    │   │     → log HOLDING → fila Excel
    │   │
    │   ├─ [QQQ] análisis completo
    │   │   ├─ Quote: $495.00 | SMA20=$480.00 | SMA50=$465.00
    │   │   │          precio > SMA20 > SMA50 → trend_strength="strong_bullish"
    │   │   │          volume_ratio=1.2x → vol_bonus=0.02
    │   │   │
    │   │   ├─ news_fetcher.fetch("QQQ", hours=4)
    │   │   │     5 titulares: "Tech rally continues", "Nasdaq breaks resistance"
    │   │   │
    │   │   ├─ sentiment_analyzer.analyze(headlines)
    │   │   │     VADER compound=+0.61 → label=positive
    │   │   │     sentiment_score = (0.61+1)/2 = 0.805
    │   │   │
    │   │   ├─ opportunity_scorer.calculate(quote, sentiment, macro)
    │   │   │     trend     : min(1.0+0.02, 1.0) × 40% = 0.400
    │   │   │     sentiment : 0.805             × 20% = 0.161
    │   │   │     macro     : 0.65              × 25% = 0.163
    │   │   │     vix       : 0.65              × 15% = 0.098
    │   │   │     TOTAL = 0.822
    │   │   │
    │   │   └─ decision_engine.evaluate()
    │   │         Regla 0: vix != extreme ✓
    │   │         Regla 1: 0.822 >= 0.70 ✓
    │   │         Regla 2: trend=bullish ✓ | sentiment=positive ✓ | macro=bullish ✓
    │   │         → 3/3 bullish → APPROVE BUY
    │   │         → size=0.05 (score 0.78–0.84 → SIZE_MEDIUM_CONFIDENCE)
    │   │
    │   ├─ [IWM, DIA, XLK, XLF, XLE, XLV] → NO_SIGNAL (scores bajos)
    │   │     → log NO_SIGNAL × 6 → filas Excel
    │   │
    │   ├─ CONSTRUCCIÓN DEL PAYLOAD (QQQ)
    │   │   signal_formatter.build_payload(result, "moderate")
    │   │   {
    │   │     "timestamp": "2026-04-27T14:45:00Z",
    │   │     "status": "pending",
    │   │     "signal": {
    │   │       "strategy_id": "bot2_swing_trailing",
    │   │       "symbol": "QQQ",
    │   │       "action": "buy",
    │   │       "confidence": 0.822,
    │   │       "size": 0.05,
    │   │       "params": {
    │   │         "source": "bot2",
    │   │         "exit_strategy": "trailing_stop",
    │   │         "trail_percent": 4.0,
    │   │         "take_profit_pct": null,
    │   │         "max_holding_days": 10,
    │   │         "vix_regime_at_entry": "moderate",
    │   │         "research_summary": "Score 0.822 | 3/3 señales alcistas | trend=strong_bullish sentiment=positive macro=bullish",
    │   │         "score_breakdown": { "sentiment":0.161, "trend":0.400, "macro":0.163, "vix":0.098 }
    │   │       }
    │   │     }
    │   │   }
    │   │
    │   └─ ENVÍO A BOT1
    │       webhook_client.send(payload)
    │       POST http://127.0.0.1:8000/webhook/bot2
    │       Header: X-Webhook-Secret: a_secure_random_string
    │
    ├─ BOT1 RECIBE Y EJECUTA
    │   ├─ Valida X-Webhook-Secret ✓
    │   ├─ strategy_id="bot2_swing_trailing" → BotRegistry ✓
    │   └─ Alpaca: BUY QQQ → filled @ $495.20
    │       Responde: {"status": "executed", "order_id": "a1b2c3d4-..."}
    │
    └─ RESULTADO
        agente01:
          ├─ _mark_signal_sent("QQQ")        → cooldown 24h activo
          ├─ _add_open_position("QQQ", ...)  → open_positions.json actualizado
          ├─ telegram_notifier.signal_sent() → ✅ Señal enviada | 4.0% trail | moderate
          ├─ _log_decision({APPROVE, order_id, trail_config})
          ├─ excel_rows += fila QQQ (webhook_status="sent")
          ├─ _write_cycle_report()            → logs/2026-04-27_14-45-00.json
          └─ append_excel_rows(excel_rows)   → trade_log.xlsx +8 filas
```

---

## Flujo B — Sin Oportunidad: Ciclo Sin Señales

```
run_cycle() — mercado abierto, ningún símbolo pasa el umbral
    │
    ├─ Macro: Fear&Greed=35 (Fear), VIX=23 (high), macro_bias=bearish
    │
    ├─ Por símbolo (todos NO_SIGNAL):
    │   ├─ SPY: trend=neutral, sentiment=neutral, compound=+0.02
    │   │       score: 0.50×0.40 + 0.51×0.20 + 0.35×0.25 + 0.30×0.15 = 0.484
    │   │       → score 0.484 < umbral 0.70 → NO_SIGNAL
    │   │
    │   ├─ QQQ: trend=bearish, sentiment=negative, compound=-0.35
    │   │       score: 0.25×0.40 + 0.33×0.20 + 0.35×0.25 + 0.30×0.15 = 0.311
    │   │       → score 0.311 < umbral 0.70 → NO_SIGNAL
    │   │
    │   └─ [IWM, DIA, XLK, XLF, XLE, XLV] → NO_SIGNAL (scores similares)
    │
    ├─ Ningún símbolo aprobado
    │
    ├─ agente01 envía no_signal a bot1:
    │   {"status":"no_signal","reason":"Ningún simbolo supera umbral 0.70 [SPY:0.484 | QQQ:0.311 | ...]"}
    │   bot1 responde: {"status": "received_no_signal"}
    │
    └─ RESULTADO
        ├─ telegram_notifier.no_signal_cycle("SPY:0.484 | QQQ:0.311 | ...") → 🔍
        ├─ _log_decision(NO_SIGNAL) × 8
        ├─ _write_cycle_report()    → logs/2026-04-27_10-00-00.json
        └─ append_excel_rows()     → trade_log.xlsx +8 filas (todas NO_SIGNAL)
```

---

## Flujo C — Cierre Forzado: Invalidación de Tesis

```
run_cycle() — SPY tiene posición abierta desde hace 3 días
    │
    ├─ FASE 1: EXIT EVALUATOR para SPY
    │   ├─ Quote fresco: trend=bearish (-1.8%), volume_ratio=1.9x
    │   ├─ Sentiment: compound=-0.63, headline_count=7
    │   │   titulares: "Fed signals aggressive hike", "SPY breaks support", "Market crash fears"
    │   │
    │   ├─ exit_evaluator.evaluate_exit(symbol="SPY", ...)
    │   │     T1: vix=22 (high, no extreme) → no cierra
    │   │     T2: trend=bearish AND vol_ratio=1.9 > 1.5 → TRIGGER ACTIVO
    │   │     → should_close=True, reason="trend_reversal_with_volume: trend=bearish, vol_ratio=1.9"
    │   │
    │   ├─ signal_formatter.build_close_payload("SPY", "trend_reversal_with_volume: ...")
    │   │   {
    │   │     "status": "pending",
    │   │     "signal": {
    │   │       "strategy_id": "bot2_swing_trailing",
    │   │       "symbol": "SPY",
    │   │       "action": "close",
    │   │       "confidence": 1.0,
    │   │       "size": 1.0,
    │   │       "params": {
    │   │         "source": "bot2",
    │   │         "close_reason": "trend_reversal_with_volume: trend=bearish, vol_ratio=1.9",
    │   │         "research_summary": "Cierre forzado: trend_reversal_with_volume"
    │   │       }
    │   │     }
    │   │   }
    │   │
    │   └─ webhook_client.send(close_payload)
    │       bot1 responde: {"status": "executed"}
    │       ├─ _remove_open_position("SPY")  → open_positions.json actualizado
    │       ├─ telegram_notifier.position_closed("SPY", "trend_reversal_with_volume") → 🚪
    │       └─ excel_rows += fila SPY (status="EXIT_FORCED", webhook_status="sent")
    │
    └─ RESULTADO
        SPY cerrado, cooldown NO se activa (el cierre libera el símbolo para próximas entradas).
        Los demás símbolos del WATCHLIST continúan con análisis normal en Fase 3.
```

---

## Flujo D — Fallo de Red: Webhook No Llega a bot1

```
webhook_client.send(payload) — QQQ APPROVE pero bot1 no responde
    │
    ├─ Intento 1: ConnectionError (bot1 no disponible)
    │   espera 5s
    │
    ├─ Intento 2: Timeout
    │   espera 10s
    │
    └─ Intento 3: ConnectionError — agotado

→ Retorna {"status": "failed", "error": "Connection refused"}

agente01:
  ├─ _save_to_pending(payload)
  │     state/pending_signals.json ← [payload_QQQ agregado]
  │
  ├─ telegram_notifier.webhook_failed("QQQ", "Connection refused") → ❌
  ├─ _log_decision({WEBHOOK_FAILED, error, score})
  └─ excel_rows fila QQQ: webhook_status="failed"

─── AL PRÓXIMO CICLO ───

run_cycle() arranca:
  webhook_client.retry_pending()
    ├─ Carga state/pending_signals.json → [payload_QQQ]
    ├─ Intenta reenviar → bot1 ya está activo
    ├─ Responde: {"status": "executed", "order_id": "..."}
    ├─ Elimina de pending_signals.json
    ├─ _mark_signal_sent("QQQ") → cooldown activado
    └─ _add_open_position("QQQ", ...)
```

---

## Flujo E — Rechazo por bot1: Estrategia Pausada

```
webhook_client.send(payload) — SPY APPROVE, bot1 recibe pero rechaza
    │
    └─ POST exitoso → bot1 responde HTTP 200:
       {"status": "rejected", "reason": "bot is paused by manager"}

agente01 detecta status="rejected":
    │
    ├─ logger.warning("bot1 rechazo la señal: bot is paused by manager")
    │
    ├─ telegram_notifier.signal_rejected("SPY", "buy", "bot is paused by manager") → ⚠️
    │
    ├─ _log_decision({REJECTED_BY_BOT1, reason, score})
    │
    ├─ excel_rows fila SPY: webhook_status="rejected"
    │
    └─ NO guarda en pending_signals.json
       NO activa cooldown (no se ejecutó)
       Respeta la decisión del manager de bot1
       La señal se descarta — la estrategia debe reactivarse manualmente en bot1
```

---

## Resumen de Decisiones Posibles

| Decisión | Condición | Bot1 recibe | Excel webhook_status |
|----------|-----------|-------------|----------------------|
| `APPROVE` + éxito | score >= 0.70 + 3/3 bullish + bot1 OK | ✅ ejecuta orden + trailing | `sent` / `dry_run` |
| `APPROVE` + fallo | bot1 inaccesible tras 3 intentos | ❌ pendiente | `failed` |
| `APPROVE` + rechazado | bot1 responde `rejected` | ❌ descartado | `rejected` |
| `NO_SIGNAL` (score bajo) | score < 0.70 | ✅ no_signal payload | `n/a` |
| `NO_SIGNAL` (VIX extremo) | VIX > 30 | ✅ no_signal payload | `n/a` |
| `NO_SIGNAL` (mixto) | señales no alineadas | ✅ no_signal payload | `n/a` |
| `HOLDING` | posición ya abierta | ❌ skip | `n/a` |
| `COOLDOWN` | señal enviada hace < 24h | ❌ skip | `n/a` |
| `NO_DATA` | yfinance no devolvió datos | ❌ skip | `n/a` |
| `EXIT_FORCED` + éxito | trigger activado, bot1 cierra | ✅ close payload | `sent` |
| `EXIT_FORCED` + fallo | trigger activado, bot1 no responde | ❌ pendiente manual | `failed` |
| `EXIT_CHECK_OK` | posición vigente, sin trigger | ❌ no se actúa | `n/a` |

**Todos los resultados quedan registrados en `logs/trade_log.xlsx`** — una fila por símbolo por ciclo, independientemente de si la operación se ejecutó en el broker o no.
