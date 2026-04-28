# Arquitectura de agente01

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              agente01.py                                │
│              (Orquestador + APScheduler — Blocking, America/New_York)   │
│                                                                         │
│   Cada CYCLE_INTERVAL_MINUTES minutos (default: 60), en horario de     │
│   mercado NYSE/NASDAQ (lun–vie 9:30–16:00 ET)                          │
│                                                                         │
│   FASE 0: retry_pending()        ← reintenta señales fallidas previas  │
│                                                                         │
│   FASE 1: EXIT EVALUATOR (por cada posición abierta)                   │
│      a. Fetch precio + noticias + sentimiento frescos                  │
│      b. exit_evaluator.evaluate_exit()                                 │
│         Trigger 1: VIX extreme      → close forzado                    │
│         Trigger 2: trend bearish + vol > 1.5x → close forzado         │
│         Trigger 3: compound < -0.5 + 5+ titulares → close forzado     │
│         Trigger 4: elapsed_days >= max_holding_days → close forzado    │
│      c. Si trigger activo → build_close_payload → webhook → bot1       │
│                                                                         │
│   FASE 2: MACRO (una vez por ciclo)                                    │
│      a. macro_indicators.get_macro_context()                           │
│      b. market_data.get_quotes(watchlist + open_positions)             │
│                                                                         │
│   FASE 3: ANÁLISIS POR SÍMBOLO (por cada símbolo en WATCHLIST)        │
│      a. Skip si posición abierta (HOLDING)                             │
│      b. Skip si en cooldown (24h)                                      │
│      c. news_fetcher.fetch() → sentimiento VADER                       │
│      d. opportunity_scorer.calculate() → score 0.0–1.0                │
│      e. decision_engine.evaluate() → APPROVE / NO_SIGNAL               │
│      f. Si APPROVE → build_payload → webhook → bot1                    │
│                                                                         │
│   FASE 4: PERSISTENCIA                                                  │
│      a. _write_cycle_report() → logs/YYYY-MM-DD_HH-MM-SS.json         │
│      b. append_excel_rows()  → logs/trade_log.xlsx                     │
│      c. _log_decision()      → state/decision_log.jsonl               │
│                                                                         │
└────────────┬────────────────────────────────────────────────────────────┘
             │
    ┌────────▼────────────────────────────────────────────────┐
    │                    RESEARCH LAYER                        │
    │                  (Capa de Investigación)                 │
    │                                                          │
    │  market_data.py                                          │
    │  ├─ yfinance.Ticker(symbol).history(period="60d")        │
    │  ├─ precio, change_pct, volume, avg_volume               │
    │  ├─ volume_ratio = volume / avg_volume                   │
    │  ├─ SMA20 (media ultimos 20 cierres)                     │
    │  ├─ SMA50 (media ultimos 50 cierres)                     │
    │  ├─ price_vs_sma20 (%)                                   │
    │  ├─ trend: "bullish"/"neutral"/"bearish"                 │
    │  └─ trend_strength: 5 niveles segun SMA20 y SMA50        │
    │                                                          │
    │  macro_indicators.py                                     │
    │  ├─ CNN Fear & Greed API (con fallback 50.0)             │
    │  │   production.dataviz.cnn.io/index/fearandgreed        │
    │  ├─ fear_greed_score (0–100), fear_greed_label           │
    │  ├─ yfinance.Ticker("^VIX") — fallback 20.0             │
    │  ├─ vix (float), vix_regime (low/moderate/high/extreme)  │
    │  └─ macro_bias (bullish/neutral/bearish)                 │
    │                                                          │
    │  news_fetcher.py                                         │
    │  ├─ NewsAPI /v2/everything                               │
    │  ├─ query: simbolo + ultimas NEWS_LOOKBACK_HOURS (4h)    │
    │  └─ lista de Headline(title, description, source, ts)    │
    └────────┬─────────────────────────────────────────────────┘
             │
    ┌────────▼────────────────────────────────────────────────┐
    │                    ANALYSIS LAYER                        │
    │                  (Capa de Análisis)                      │
    │                                                          │
    │  sentiment_analyzer.py                                   │
    │  ├─ VADER NLP sobre cada titular (corre local)           │
    │  ├─ compound = promedio de scores (-1.0 a +1.0)          │
    │  └─ label: positive(>=0.05) / neutral / negative(<=-0.05)│
    │                                                          │
    │  opportunity_scorer.py                                   │
    │  ├─ trend_score    = strength_map[trend_strength]+bonus  × 40%│
    │  ├─ sentiment_score = (compound+1)/2                     × 20%│
    │  ├─ macro_score    = fear_greed/100                      × 25%│
    │  ├─ vix_score      = low=1.0/mod=0.65/high=0.30/ext=0.0 × 15%│
    │  └─ total          = suma ponderada (0.0–1.0)            │
    │                                                          │
    │  decision_engine.py                                      │
    │  ├─ Regla 0: vix_regime=="extreme" → NO_SIGNAL           │
    │  ├─ Regla 1: total < 0.70 → NO_SIGNAL                   │
    │  ├─ Regla 2: consenso 3/3 bullish → APPROVE BUY         │
    │  │   (trend=="bullish" + sentiment=="positive" + macro=="bullish")│
    │  └─ Tamaño dinámico:                                     │
    │      score >=0.85 → size=0.08 (8% del portafolio)       │
    │      score >=0.78 → size=0.05 (5%)                      │
    │      score >=0.70 → size=0.03 (3%)                      │
    │                                                          │
    │  exit_evaluator.py                                       │
    │  ├─ Trigger 1: vix_regime=="extreme" → close             │
    │  ├─ Trigger 2: trend=="bearish" AND vol_ratio>1.5 → close│
    │  ├─ Trigger 3: compound<-0.5 AND >=5 titulares → close   │
    │  └─ Trigger 4: elapsed_days>=max_holding_days → close    │
    └────────┬─────────────────────────────────────────────────┘
             │
    ┌────────▼────────────────────────────────────────────────┐
    │                     SENDER LAYER                         │
    │                   (Capa de Envío)                        │
    │                                                          │
    │  signal_formatter.py                                     │
    │  ├─ get_trail_config(vix_regime) → {trail%, tp%, days}   │
    │  ├─ APPROVE → build_payload(result, vix_regime)          │
    │  │   strategy_id: "bot2_swing_trailing"                  │
    │  │   source: "bot2"                                      │
    │  │   exit_strategy: "trailing_stop"                      │
    │  │   trail_percent: 3.0/4.0/5.5 segun VIX               │
    │  │   take_profit_pct: null o 8.0 segun VIX              │
    │  │   vix_regime_at_entry, max_holding_days               │
    │  │   score_breakdown: {trend, sentiment, macro, vix}     │
    │  ├─ EXIT → build_close_payload(symbol, close_reason)     │
    │  │   action: "close", confidence: 1.0, size: 1.0         │
    │  └─ NO_SIGNAL → build_no_signal_payload(reason)          │
    │                                                          │
    │  webhook_client.py                                       │
    │  ├─ DRY_RUN=true  → solo loguea, no envía               │
    │  ├─ POST a http://127.0.0.1:8000/webhook/bot2            │
    │  │   Header: X-Webhook-Secret                            │
    │  ├─ backoff exponencial: 5s → 10s → 15s (3 intentos)    │
    │  ├─ status="executed"           → exito, cooldown activo │
    │  ├─ status="rejected"           → log + Telegram ⚠️      │
    │  ├─ status="received_no_signal" → confirmación OK        │
    │  └─ status="failed"             → pending_signals.json   │
    │                                                          │
    │  telegram_notifier.py                                    │
    │  ├─ signal_sent()       → ✅ señal aprobada              │
    │  ├─ signal_rejected()   → ⚠️ rechazada por bot1          │
    │  ├─ webhook_failed()    → ❌ fallo de red, en cola        │
    │  ├─ position_closed()   → 🚪 cierre forzado por trigger  │
    │  └─ no_signal_cycle()   → 🔍 ciclo sin señales + scores  │
    └────────┬─────────────────────────────────────────────────┘
             │ HTTP POST 127.0.0.1:8000/webhook/bot2
             │ Header: X-Webhook-Secret = WEBHOOK_SECRET
             ▼
    ┌────────────────────────────────────────────────────────┐
    │                   bot1 (Trading-bot)                   │
    │         FastAPI corriendo en el mismo PC               │
    │                                                        │
    │  Valida X-Webhook-Secret                               │
    │  Parsea signal.strategy_id → BotRegistry              │
    │  Ejecuta orden en Alpaca Paper/Live API                │
    │  Responde: executed | rejected | received_no_signal    │
    └────────────────────────────────────────────────────────┘
```

---

## Capa de Estado (Persistencia)

```
state/
├── last_signals.json
│   { "SPY": "2026-04-27T14:00:00Z", "QQQ": "2026-04-27T14:00:01Z" }
│   Control de cooldown (24h por simbolo).
│   Solo se actualiza cuando bot1 confirma "executed".
│
├── open_positions.json
│   {
│     "SPY": {
│       "opened_at": "2026-04-27T14:00:00Z",
│       "vix_regime_at_entry": "moderate",
│       "max_holding_days": 10,
│       "action": "buy",
│       "confidence": 0.813,
│       "size": 0.05
│     }
│   }
│   Posiciones activas. Evita dobles entradas y habilita exit_evaluator.
│   Se agrega cuando bot1 confirma "executed".
│   Se elimina cuando se envía un cierre forzado exitoso.
│
├── pending_signals.json
│   [ { payload_spy }, ... ]
│   Señales fallidas (3 intentos agotados).
│   retry_pending() las reenvía al inicio del proximo ciclo.
│
└── decision_log.jsonl
    Una linea JSON por decision. Append-only.
    Tipos: APPROVE | NO_SIGNAL | HOLDING | COOLDOWN | NO_DATA |
           EXIT_FORCED | EXIT_CHECK_OK | WEBHOOK_FAILED | REJECTED_BY_BOT1
```

---

## Reportes de Ciclo

```
logs/
├── YYYY-MM-DD_HH-MM-SS.json
│   Reporte completo por cada ejecucion:
│   ├── cycle_id, started_at, finished_at, duration_seconds
│   ├── mode (DRY_RUN / LIVE)
│   ├── priority_cycle (bool) — 09:45, 12:30 o 15:30 ET
│   ├── market_open (bool)
│   ├── macro { fear_greed_score, vix, vix_regime, macro_bias }
│   ├── symbols {
│   │     SPY: { status, quote, headlines, sentiment, score, decision, webhook_response }
│   │     QQQ: { status: "HOLDING", position: {...} }
│   │     IWM: { status: "COOLDOWN" }
│   │   }
│   └── summary { approved[], exits[], no_signal[], cooldown[], holding[], no_data[], ... }
│
└── trade_log.xlsx
    Registro Excel acumulativo. Una fila por simbolo por ciclo.
    Columnas: timestamp, cycle_id, mode, symbol, status, decision, action,
              precio, change_pct, sma20, sma50, trend_strength, volume_ratio,
              sentiment_compound, label, fear_greed, vix, vix_regime,
              score_trend, score_sentiment, score_macro, score_vix, score_total,
              confidence, size, trail_percent, take_profit_pct, max_holding_days,
              reason, webhook_status
```

---

## Scheduler (APScheduler BlockingScheduler)

- **Trigger**: `interval` cada `CYCLE_INTERVAL_MINUTES` minutos (default: 60)
- **Timezone**: `America/New_York` (ET) — maneja DST automaticamente
- **Ciclo inmediato**: Al arrancar, ejecuta un ciclo antes de programar el siguiente
- **Guard de mercado**: Fuera del horario 9:30–16:00 ET (lun–vie) → ciclo omitido, reporte escrito
- **Ciclos prioritarios**: 09:45, 12:30, 15:30 ET marcados `[PRIORITY]` en logs

**Horario en Lima (UTC-5, sin DST):**
- Durante EDT (Mar–Nov): mercado 08:30–15:00 Lima
- Durante EST (Nov–Mar): mercado 09:30–16:00 Lima
- El agente se sincroniza automáticamente — no requiere ajuste manual

---

## Fuentes de Datos

| Fuente | Módulo | API Key | Coste | Fallback |
|--------|--------|---------|-------|---------|
| Yahoo Finance (precios, 60d) | market_data.py | No | Gratis | `None` → símbolo saltado |
| Yahoo Finance (^VIX) | macro_indicators.py | No | Gratis | VIX = 20.0 |
| CNN Fear & Greed | macro_indicators.py | No | Gratis | score = 50.0 |
| NewsAPI (4h window) | news_fetcher.py | Si | Gratis (100/día) | Lista vacía → neutral |
| VADER NLP | sentiment_analyzer.py | No (local) | Gratis | neutral si 0 titulares |
| Telegram Bot API | telegram_notifier.py | Si (opcional) | Gratis | No-op si vacío |

---

## Integración con bot1

| Campo | Valor |
|---|---|
| URL | `http://127.0.0.1:8000/webhook/bot2` |
| Header | `X-Webhook-Secret: {WEBHOOK_SECRET}` |
| `strategy_id` | `"bot2_swing_trailing"` |
| `params.source` | `"bot2"` |
| `params.exit_strategy` | `"trailing_stop"` |
| `params.trail_percent` | `3.0` / `4.0` / `5.5` segun vix_regime |
| `params.vix_regime_at_entry` | `"low"` / `"moderate"` / `"high"` |
| `params.research_summary` | Razón legible de la decisión |
| `params.score_breakdown` | `{trend, sentiment, macro, vix}` — contribuciones ponderadas |

agente01 **no modifica bot1**. Se integra usando el contrato de webhook que bot1 ya tiene definido para el endpoint `/webhook/bot2`.
