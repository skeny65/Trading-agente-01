# Flujos End-to-End — agente01 (SPY Specialist)

agente01 tiene 5 flujos posibles en cada ciclo. Todos son exclusivamente sobre SPY.

---

## Flujo A — Caso Feliz: SPY Aprobado y Ejecutado

```
APScheduler dispara run_cycle() — 09:45 ET [PRIORITY]
    │
    ├─ FASE 0: retry_pending() — sin señales pendientes (queue vacío)
    │
    ├─ FASE 1: EXIT EVALUATOR
    │   └─ No hay posición SPY abierta → skip
    │
    ├─ SPY sin posición abierta → análisis completo
    │
    ├─ spy_cycle.run("SPY")
    │   │
    │   ├─ DIMENSIÓN 1 — Macro (25%)
    │   │   fred_client.get_macro_score()
    │   │     CPI yoy = 3.1% (bajando) → positivo
    │   │     Fed Funds Rate = 5.25% estable → neutral
    │   │     Yield spread (10Y-2Y) = +0.15% → curva positiva
    │   │     NFP = +175k → sólido
    │   │     → macro_score = 0.62
    │   │
    │   ├─ DIMENSIÓN 2 — Técnico (20%)
    │   │   multi_timeframe.analyze("SPY") — Yahoo + Twelve Data simultáneos
    │   │     1D: RSI=58, precio > SMA200 → bullish ✓
    │   │     4H: MACD histograma positivo → bullish ✓
    │   │     1H: precio en banda media BB → neutral
    │   │     bullish_count = 2/3
    │   │     → technical_score = 0.81
    │   │
    │   ├─ DIMENSIÓN 3 — Componentes (20%)
    │   │   top_holdings + sectors — Yahoo batch + Twelve Data rellena huecos
    │   │     Top-10: AAPL+1.2%, MSFT+0.8%, NVDA+2.1%, AMZN+0.5% → 8/10 positivos
    │   │     Sectores: XLK+1.5%, XLF+0.7%, XLV+0.3%, XLI+0.8% → 9/11 positivos
    │   │     sector_breadth = 0.82 → positivo
    │   │     → components_score = 0.74
    │   │
    │   ├─ DIMENSIÓN 4 — Sentimiento (15%)
    │   │   vix_term_structure → contango (VX1 > VIX) → 0.85
    │   │   put_call_ratio = 0.72 → neutral/positivo → 0.65
    │   │   fear_greed = 65 (Greed) → 0.65
    │   │   vader compound = +0.52 → 0.76
    │   │   → sentiment_score = 0.30×0.85 + 0.25×0.65 + 0.25×0.65 + 0.20×0.76 = 0.73
    │   │
    │   ├─ DIMENSIÓN 5 — Eventos (10%)
    │   │   FOMC: próxima reunión en 18 días → sin veto
    │   │   CPI release: en 9 días → sin impacto inmediato
    │   │   Reuters RSS: sin eventos geopolíticos < 12h
    │   │   → events_score = 0.80, score_multiplier = 1.0, veto = False
    │   │
    │   ├─ DIMENSIÓN 6 — Cross-Assets (10%)
    │   │   correlations.py — Yahoo + Twelve Data simultáneos
    │   │   DXY: -0.3% (dólar debilitándose = favorable SPY)
    │   │   TLT: +0.5% (yields bajando = favorable equities)
    │   │   HYG: +0.4% (apetito riesgo = positivo)
    │   │   QQQ: +1.2% (Nasdaq lidera = confirma)
    │   │   BTC: +2.8% (risk-on = positivo)
    │   │   → cross_asset_score = 0.78
    │   │
    │   ├─ filters.evaluate(dim_scores, market_data)
    │   │
    │   │   PASO 1 — VETOS DUROS:
    │   │     VIX = 16.5 (< 30) ✓
    │   │     FOMC en 18 días (no < 24h) ✓
    │   │     Earnings top-10: 0 en 48h (< 3) ✓
    │   │     RSI 1D = 58 (< 75) ✓
    │   │     SPY = $590 > SMA200=$530 ✓
    │   │     Yield spread = +0.15% (> -0.50%) ✓
    │   │     → Sin vetos duros
    │   │
    │   │   PASO 2 — SCORE COMPUESTO:
    │   │     TOTAL = 0.62×0.25 + 0.81×0.20 + 0.74×0.20
    │   │           + 0.73×0.15 + 0.80×0.10 + 0.78×0.10
    │   │           = 0.155 + 0.162 + 0.148 + 0.110 + 0.080 + 0.078
    │   │           = 0.733
    │   │
    │   │   PASO 3 — MULTIPLICADOR EVENTOS:
    │   │     Sin eventos HIGH < 24h → multiplicador = 1.0
    │   │     score_ajustado = 0.733 × 1.0 = 0.733
    │   │
    │   │   PASO 4 — GATE:
    │   │     0.733 >= MIN_CONFIDENCE (0.72) ✓
    │   │     dimensiones > 0.55: macro(0.62)✓ técnico(0.81)✓ compon.(0.74)✓
    │   │                         sentim.(0.73)✓ eventos(0.80)✓ cross(0.78)✓ → 6/6 ✓
    │   │     → FilterResult(approved=True, score=0.733, dimensions_passing=6)
    │   │
    │   └─ claude_analyst.analyze(filter_result, market_snapshot)
    │       System prompt (cacheado, ~$0.0001 de cache hit):
    │         "Eres el analista final de SPY Specialist..."
    │       User content: snapshot completo de las 6 dimensiones + VIX + scores
    │       Claude responde (JSON):
    │         {
    │           "decision": "APPROVE",
    │           "action": "buy",
    │           "confidence": 0.733,
    │           "size": 0.12,
    │           "trail_percent": 4.0,
    │           "reasoning": "Strong technical + cross-asset confirmation. Macro improving. All 6 dimensions passing. Risk/reward favorable at current VIX=16.5."
    │         }
    │       → ClaudeAnalysis(decision="APPROVE", confidence=0.733, size=0.12, trail=4.0)
    │
    ├─ SpyCycleResult:
    │     decision="APPROVE" | confidence=0.733 | size=0.12 | trail_percent=4.0
    │     vix_regime="moderate" | vix_value=16.5
    │     claude_reasoning="Strong technical + cross-asset confirmation..."
    │     dimension_scores: {macro:0.62, technical:0.81, components:0.74,
    │                        sentiment:0.73, events:0.80, cross_asset:0.78}
    │
    ├─ CONSTRUCCIÓN DEL PAYLOAD
    │   signal_formatter.build_spy_payload(result, "moderate")
    │   {
    │     "timestamp": "2026-04-27T14:45:00Z",
    │     "status": "pending",
    │     "signal": {
    │       "strategy_id": "bot2_swing_trailing",
    │       "symbol": "SPY",
    │       "action": "buy",
    │       "confidence": 0.733,
    │       "size": 0.12,
    │       "params": {
    │         "source": "bot2_spy_specialist",
    │         "exit_strategy": "trailing_stop",
    │         "trail_percent": 4.0,
    │         "take_profit_pct": null,
    │         "max_holding_days": 10,
    │         "vix_regime_at_entry": "moderate",
    │         "research_summary": "Score 0.733 | 6/6 dimensiones > 0.55 | size=12% | trail=4.0%",
    │         "claude_reasoning": "Strong technical + cross-asset confirmation...",
    │         "score_breakdown": {
    │           "macro":0.62, "technical":0.81, "components":0.74,
    │           "sentiment":0.73, "events":0.80, "cross_asset":0.78
    │         }
    │       }
    │     }
    │   }
    │
    ├─ webhook_client.send(payload)
    │   POST http://127.0.0.1:8000/webhook/bot2
    │   Header: X-Webhook-Secret
    │
    ├─ BOT1 RECIBE Y EJECUTA
    │   ├─ Valida X-Webhook-Secret ✓
    │   ├─ strategy_id="bot2_swing_trailing" → BotRegistry ✓
    │   └─ Alpaca: BUY SPY → filled @ $590.20
    │       Responde: {"status": "executed", "order_id": "a1b2c3d4-..."}
    │
    └─ RESULTADO
        agente01:
          ├─ _add_open_position("SPY", ...)  → open_positions.json actualizado
          ├─ _mark_signal_sent("SPY")        → cooldown activo
          ├─ telegram_notifier.signal_sent() → ✅ Señal enviada | 4.0% trail | moderate
          ├─ _log_decision({APPROVE, order_id, trail_config, dimension_scores})
          ├─ excel_rows: fila SPY (6 dims + claude_reasoning, webhook_status="sent")
          ├─ _write_cycle_report()           → logs/2026-04-27_14-45-00.json
          └─ append_excel_rows(excel_rows)  → trade_log.xlsx +1 fila
```

---

## Flujo B — Sin Oportunidad: Ciclo Sin Señal

```
run_cycle() — mercado abierto, SPY no pasa los filtros
    │
    ├─ spy_cycle.run("SPY")
    │   │
    │   ├─ Dimensiones calculadas:
    │   │     macro=0.42 | technical=0.48 | components=0.51
    │   │     sentiment=0.39 | events=0.70 | cross_asset=0.44
    │   │
    │   ├─ filters.evaluate()
    │   │   PASO 1 — VETOS DUROS:
    │   │     VIX = 22 (< 30) ✓ — sin veto extremo
    │   │     Pero RSI 1D = 71 < 75 ✓, SMA200 OK ✓
    │   │     → Sin vetos duros
    │   │
    │   │   PASO 2 — SCORE COMPUESTO:
    │   │     TOTAL = 0.42×0.25 + 0.48×0.20 + 0.51×0.20
    │   │           + 0.39×0.15 + 0.70×0.10 + 0.44×0.10
    │   │           = 0.105 + 0.096 + 0.102 + 0.059 + 0.070 + 0.044
    │   │           = 0.476
    │   │
    │   │   PASO 4 — GATE:
    │   │     0.476 < MIN_CONFIDENCE (0.72) ✗
    │   │     → FilterResult(approved=False, reason="score_below_threshold")
    │   │     → NO_SIGNAL (sin llamar a Claude)
    │   │
    │   └─ SpyCycleResult(decision="NO_SIGNAL", confidence=0.476, ...)
    │
    ├─ agente01 envía no_signal a bot1:
    │   {"status":"no_signal","reason":"Score 0.476 < umbral 0.72 [macro=0.42 técnico=0.48 sentimiento=0.39]"}
    │   bot1 responde: {"status": "received_no_signal"}
    │
    └─ RESULTADO
        ├─ telegram_notifier.no_signal_cycle("SPY: score=0.476") → 🔍
        ├─ _log_decision(NO_SIGNAL)
        ├─ _write_cycle_report()    → logs/2026-04-27_10-00-00.json
        └─ append_excel_rows()      → trade_log.xlsx +1 fila (NO_SIGNAL)
```

---

## Flujo B2 — Veto Duro Activo

```
run_cycle() — VIX ha subido a 31.5 (extreme)
    │
    ├─ spy_cycle.run("SPY")
    │   ├─ Dimensiones calculadas (todas neutras/positivas)
    │   ├─ filters.evaluate()
    │   │   PASO 1 — VETOS DUROS:
    │   │     VIX = 31.5 > 30 → VETO ACTIVO
    │   │     → FilterResult(approved=False, reason="veto_duro: VIX > 30", hard_veto=True)
    │   │
    │   └─ SpyCycleResult(decision="NO_SIGNAL", reason="veto_duro: VIX extremo")
    │
    └─ No se llama a Claude (vetos duros son definitivos)
       Log: "NO_SIGNAL: veto_duro — VIX=31.5 > 30"
       Excel: 1 fila NO_SIGNAL con dim_* vacíos (veto antes del score)
```

---

## Flujo B3 — Claude Veta la Señal

```
run_cycle() — filtros pasan pero Claude detecta inconsistencia
    │
    ├─ spy_cycle.run("SPY")
    │   ├─ Dimensiones: score=0.735, 5/6 dims > 0.55
    │   ├─ filters.evaluate() → approved=True
    │   │
    │   └─ claude_analyst.analyze(filter_result, market_snapshot)
    │       Claude analiza:
    │         "Score técnico alto (0.82) pero macro_score=0.48 con CPI en 4.8%
    │          y Fed en modo restrictivo. Yield curve invertida -0.45%.
    │          El componente técnico puede ser un rebote en tendencia bajista macro.
    │          Veto la señal — riesgo/recompensa desfavorable."
    │       Claude responde: {"decision": "NO_SIGNAL", ...}
    │
    └─ SpyCycleResult(decision="NO_SIGNAL",
                       claude_reasoning="Score técnico alto pero macro restrictivo...")
       Log: "Claude vetó APPROVE → NO_SIGNAL"
       Excel: 1 fila NO_SIGNAL con claude_reasoning completo
```

---

## Flujo C — Cierre Forzado: Invalidación de Tesis

```
run_cycle() — SPY tiene posición abierta desde hace 3 días
    │
    ├─ FASE 1: EXIT EVALUATOR para SPY
    │   ├─ Quote fresco: trend=bearish (-2.1%), volume_ratio=1.9x
    │   ├─ Sentiment: compound=-0.63, headline_count=7
    │   │   titulares: "Fed signals aggressive hike", "SPY breaks support"
    │   │
    │   ├─ exit_evaluator.evaluate_exit(symbol="SPY", ...)
    │   │     T1: vix=22 (high, no extreme) → no cierra
    │   │     T2: trend=bearish AND vol_ratio=1.9 > 1.5 → TRIGGER ACTIVO
    │   │     → should_close=True, reason="trend_reversal_with_volume: trend=bearish, vol_ratio=1.9"
    │   │
    │   ├─ signal_formatter.build_close_payload("SPY", "trend_reversal_with_volume: ...")
    │   └─ webhook_client.send(close_payload)
    │       bot1 responde: {"status": "executed"}
    │       ├─ _remove_open_position("SPY")  → open_positions.json actualizado
    │       ├─ telegram_notifier.position_closed("SPY", "trend_reversal_with_volume") → 🚪
    │       └─ excel_rows: fila SPY (status="EXIT_FORCED", webhook_status="sent")
    │
    ├─ SPY cerrado → ciclo no realiza nuevo análisis de entrada
    │   (el exit evaluator y el análisis de entrada son mutuamente excluyentes)
    │
    └─ RESULTADO
        SPY cerrado. El próximo ciclo volverá a analizar SPY para nueva entrada.
```

---

## Flujo D — Fallo de Red: Webhook No Llega a bot1

```
webhook_client.send(payload) — SPY APPROVE pero bot1 no responde
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
  │     state/pending_signals.json ← [payload_SPY agregado]
  │
  ├─ telegram_notifier.webhook_failed("SPY", "Connection refused") → ❌
  ├─ _log_decision({WEBHOOK_FAILED, error, score})
  └─ excel_rows fila SPY: webhook_status="failed"

─── AL PRÓXIMO CICLO ───

run_cycle() arranca:
  webhook_client.retry_pending()
    ├─ Carga state/pending_signals.json → [payload_SPY]
    ├─ Intenta reenviar → bot1 ya está activo
    ├─ Responde: {"status": "executed", "order_id": "..."}
    ├─ Elimina de pending_signals.json
    ├─ _mark_signal_sent("SPY") → cooldown activado
    └─ _add_open_position("SPY", ...)
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
    ├─ telegram_notifier.signal_rejected("SPY", "buy", "bot is paused by manager") → ⚠️
    ├─ _log_decision({REJECTED_BY_BOT1, reason, score})
    ├─ excel_rows fila SPY: webhook_status="rejected"
    │
    └─ NO guarda en pending_signals.json
       NO activa cooldown (no se ejecutó)
       NO agrega a open_positions.json
       Respeta la decisión del manager de bot1
```

---

## Resumen de Decisiones Posibles

| Decisión | Condición | Bot1 recibe | Excel webhook_status |
|----------|-----------|-------------|----------------------|
| `APPROVE` + éxito | Filtros + gate + Claude OK + bot1 OK | ✅ ejecuta buy + trailing | `sent` / `dry_run` |
| `APPROVE` + fallo | bot1 inaccesible tras 3 intentos | ❌ pendiente | `failed` |
| `APPROVE` + rechazado | bot1 responde `rejected` | ❌ descartado | `rejected` |
| `NO_SIGNAL` (veto duro) | VIX>30 / FOMC / RSI>75 / bajo SMA200 / etc | ✅ no_signal payload | `n/a` |
| `NO_SIGNAL` (score bajo) | score ajustado < 0.72 | ✅ no_signal payload | `n/a` |
| `NO_SIGNAL` (dims insuf.) | < 5 dimensiones > 0.55 | ✅ no_signal payload | `n/a` |
| `NO_SIGNAL` (Claude veto) | Claude rechaza APPROVE | ✅ no_signal payload | `n/a` |
| `HOLDING` | Posición SPY ya abierta | ❌ skip | `n/a` |
| `EXIT_FORCED` + éxito | Trigger activado, bot1 cierra | ✅ close payload | `sent` |
| `EXIT_FORCED` + fallo | Trigger activado, bot1 no responde | ❌ pendiente manual | `failed` |
| `EXIT_CHECK_OK` | Posición vigente, sin trigger | ❌ no se actúa | `n/a` |

**Todos los resultados quedan registrados en `logs/trade_log.xlsx`** — una fila por ciclo con las 6 dimensiones de análisis.
