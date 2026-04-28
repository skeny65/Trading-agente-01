# Flujos End-to-End — agente01

agente01 tiene 4 flujos posibles en cada ciclo, dependiendo del resultado del análisis y del estado de bot1.

---

## Flujo A — Caso Feliz: Oportunidad Detectada y Ejecutada

```
APScheduler dispara run_cycle()
    │
    ├─ PASO 0: retry_pending() — reenvía señales fallidas anteriores (si las hay)
    │
    ├─ PASO 1: INVESTIGACIÓN MACRO (una vez por ciclo)
    │   ├─ macro_indicators.get_macro_context()
    │   │     CNN Fear&Greed=72 (Greed) → macro_score=0.72
    │   │     VIX=14.2 (low)            → news_score=1.0
    │   │     macro_bias=bullish (F&G≥60 y VIX<20)
    │   │
    │   └─ market_data.get_quotes(["SPY", "QQQ"])
    │         SPY: $512.30 (+1.2%) | SMA20=$498.50 | trend=bullish | vol_ratio=1.4x
    │
    ├─ PASO 2: ANÁLISIS POR SÍMBOLO (SPY)
    │   ├─ news_fetcher.fetch("SPY", hours=6)
    │   │     12 titulares: "Fed signals pause", "SPY breaks resistance"
    │   │
    │   ├─ sentiment_analyzer.analyze(headlines)
    │   │     VADER compound=+0.68 → label=positive
    │   │     sentiment_score = (0.68+1)/2 = 0.84
    │   │
    │   ├─ opportunity_scorer.calculate(quote, sentiment, macro)
    │   │     sentiment : 0.84 × 30% = 0.252
    │   │     trend     : 1.0  × 30% = 0.300  (bullish + vol_bonus=0)
    │   │     macro     : 0.72 × 25% = 0.180  (Fear&Greed=72)
    │   │     news      : 1.0  × 15% = 0.150  (VIX=14.2, low)
    │   │     TOTAL = 0.882
    │   │
    │   └─ decision_engine.evaluate()
    │         Regla 1: 0.882 ≥ 0.65 ✓
    │         Regla 2: trend=bullish ✓ | sentiment=positive ✓ | macro=bullish ✓
    │         → 3/3 bullish → APPROVE BUY
    │         → size=0.15 (score ≥ 0.85)
    │
    ├─ PASO 3: CONSTRUCCIÓN DEL PAYLOAD
    │   signal_formatter.build_payload(result)
    │   {
    │     "timestamp": "2026-04-27T14:00:00Z",
    │     "status": "pending",
    │     "processed": false,
    │     "signal": {
    │       "strategy_id": "bot2_macro_research",
    │       "symbol": "SPY",
    │       "action": "buy",
    │       "confidence": 0.882,
    │       "size": 0.15,
    │       "params": {
    │         "source": "bot2",
    │         "stop_loss": 0.02,
    │         "take_profit": 0.04,
    │         "research_summary": "Score 0.882 | 3/3 señales alcistas | trend=bullish sentiment=positive macro=bullish",
    │         "score_breakdown": {
    │           "sentiment": 0.252,
    │           "trend":     0.300,
    │           "macro":     0.180,
    │           "news":      0.150
    │         }
    │       }
    │     }
    │   }
    │
    ├─ PASO 4: ENVÍO A BOT1
    │   webhook_client.send(payload)
    │   POST http://127.0.0.1:8000/webhook/bot2
    │   Header: X-Webhook-Secret: a_secure_random_string
    │
    ├─ PASO 5: BOT1 RECIBE Y EJECUTA
    │   ├─ Valida X-Webhook-Secret ✓
    │   ├─ Parsea signal.strategy_id → "bot2_macro_research"
    │   ├─ Consulta BotRegistry: estrategia activa ✓
    │   └─ Alpaca: BUY SPY → filled @ $512.35
    │       Responde: {"status": "executed", "order_id": "d43f5925-..."}
    │
    └─ PASO 6: RESULTADO
        agente01:
          ├─ _mark_signal_sent("SPY")  → cooldown activo por COOLDOWN_HOURS
          ├─ telegram_notifier.signal_sent("SPY", "buy", 0.882, 0.15) → ✅
          ├─ _log_decision({decision:"APPROVE", order_id:"d43f5925-..."})
          └─ _write_cycle_report() → logs/2026-04-27_14-00-00.json
```

---

## Flujo B — Sin Oportunidad: Ciclo Sin Señales

```
run_cycle() para SPY y QQQ
    │
    ├─ SPY: score=0.45 (noticias mixtas, tendencia lateral)
    │   decision_engine → NO_SIGNAL: "Score 0.450 < umbral 0.65"
    │
    └─ QQQ: score=0.38 (noticias negativas, VIX moderado)
        decision_engine → NO_SIGNAL: "Score 0.380 < umbral 0.65"

→ Ningún símbolo aprobado

agente01 envía no_signal a bot1:
{
  "timestamp": "2026-04-27T10:00:00Z",
  "status": "no_signal",
  "processed": false,
  "reason": "Ningún símbolo supera umbral 0.65 [SPY:0.45 | QQQ:0.38]",
  "signal": null
}

bot1 responde: {"status": "received_no_signal", "processed": true}

agente01:
  ├─ Loguea cada NO_SIGNAL individualmente en decision_log.jsonl
  ├─ telegram_notifier.no_signal_cycle("Ningún símbolo supera... [SPY:0.45 | QQQ:0.38]") → 🔍
  └─ _write_cycle_report() → logs/2026-04-27_10-00-00.json

bot1: NO ejecuta ninguna orden (solo registra el no_signal en su log).
```

---

## Flujo C — Fallo de Red: Webhook No Llega a bot1

```
webhook_client.send(payload)
    │
    ├─ Intento 1: ConnectionError (bot1 no disponible)
    │   espera 5s (backoff ×1)
    │
    ├─ Intento 2: Timeout
    │   espera 10s (backoff ×2)
    │
    └─ Intento 3: ConnectionError
        espera 15s — agotado

→ Retorna {"status": "failed", "error": "Connection refused"}

agente01:
  ├─ _save_to_pending(payload)
  │     state/pending_signals.json ← [payload agregado]
  │
  ├─ telegram_notifier.webhook_failed("SPY", "Connection refused") → ❌
  │
  └─ _log_decision({decision: "WEBHOOK_FAILED", error: "Connection refused"})

─── AL PRÓXIMO CICLO ───

run_cycle() arranca:
  webhook_client.retry_pending()
    ├─ Carga state/pending_signals.json → [payload_SPY]
    ├─ Intenta reenviar: POST 127.0.0.1:8000/webhook/bot2
    ├─ Si tiene éxito → elimina de pending_signals.json
    └─ Si falla de nuevo → permanece para el siguiente ciclo
```

---

## Flujo D — Rechazo por bot1: Estrategia Pausada

```
webhook_client.send(payload)
    │
    └─ POST exitoso → bot1 responde HTTP 200:
       {"status": "rejected", "reason": "bot is paused by manager"}

agente01 detecta status="rejected":
    │
    ├─ logger.warning("bot1 rechazó la señal: bot is paused by manager")
    │
    ├─ telegram_notifier.signal_rejected("SPY", "buy", "bot is paused by manager") → ⚠️
    │
    ├─ _log_decision({decision: "REJECTED_BY_BOT1", reason: "bot is paused by manager"})
    │
    └─ NO guarda en pending_signals.json
       NO reintenta — respeta la decisión del manager de bot1

Resultado: señal descartada intencionalmente.
La estrategia debe reactivarse manualmente en bot1.
```

---

## Resumen de Decisiones Posibles

| Decisión | Condición | ¿Bot1 recibe? | Acción de agente01 |
|----------|-----------|---------------|--------------------|
| `APPROVE` + éxito | score ≥ MIN_CONFIDENCE + ≥2/3 bullish + bot1 OK | ✅ ejecuta orden | Cooldown + Telegram ✅ + log |
| `NO_SIGNAL` (score bajo) | score < MIN_CONFIDENCE | ✅ no_signal | Log + Telegram 🔍 |
| `NO_SIGNAL` (mixto/bajista) | señales divergentes o ≥2 bearish | ✅ no_signal | Log + Telegram 🔍 |
| `WEBHOOK_FAILED` | bot1 inaccesible tras 3 intentos | ❌ | Pending + Telegram ❌ + log |
| `REJECTED_BY_BOT1` | bot1 responde rejected | ✅ pero rechaza | Telegram ⚠️ + log (no reintenta) |
| `COOLDOWN` | señal enviada hace < COOLDOWN_HOURS | ❌ | Skip silencioso |
| `NO_DATA` | yfinance no devolvió datos | ❌ | Skip + log |
