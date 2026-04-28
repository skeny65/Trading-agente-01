# Arquitectura de agente01

## Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              agente01.py                                │
│                        (Orquestador + APScheduler)                      │
│                                                                         │
│   Cada CYCLE_INTERVAL_HOURS horas (default: 4h), en horario de mercado  │
│                                                                         │
│   1. retry_pending()      ← reintenta señales fallidas del ciclo previo │
│   2. get_macro_context()  ← macro compartido para todos los símbolos    │
│   3. get_quotes()         ← datos de precio por símbolo                 │
│   4. Por cada símbolo en WATCHLIST:                                     │
│      a. cooldown check                                                  │
│      b. fetch headlines (NewsAPI)                                       │
│      c. analyze sentiment (VADER)                                       │
│      d. calculate score (4 componentes ponderados)                      │
│      e. evaluate decision (umbral + consenso 2/3)                       │
│      f. send webhook / log                                              │
│   5. Si ningún símbolo aprobado → envía no_signal a bot1               │
│   6. Escribe reporte completo en logs/YYYY-MM-DD_HH-MM-SS.json         │
└────────────┬────────────────────────────────────────────────────────────┘
             │
    ┌────────▼────────────────────────────────────────────────┐
    │                    RESEARCH LAYER                        │
    │                  (Capa de Investigación)                 │
    │                                                          │
    │  market_data.py              macro_indicators.py         │
    │  ├─ yfinance.Ticker(symbol)  ├─ CNN Fear & Greed API     │
    │  ├─ historial 30 días        │   production.dataviz.cnn  │
    │  ├─ price, change_pct        ├─ fear_greed_score (0–100) │
    │  ├─ volume, avg_volume       ├─ fear_greed_label         │
    │  ├─ volume_ratio             ├─ yfinance.Ticker("^VIX")  │
    │  ├─ SMA20 (20 cierres)       ├─ vix (float)              │
    │  ├─ price_vs_sma20 (%)       ├─ vix_regime               │
    │  └─ trend: bull/bear/neutral └─ macro_bias: bull/bear/neu│
    │                                                          │
    │  news_fetcher.py                                         │
    │  ├─ NewsAPI /v2/everything                               │
    │  ├─ query: símbolo + últimas N horas                     │
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
    │  └─ label: positive(≥0.05) / neutral / negative(≤-0.05) │
    │                                                          │
    │  opportunity_scorer.py                                   │
    │  ├─ sentiment_score = (compound+1)/2        × 30%        │
    │  ├─ trend_score     = bull=1.0/neu=0.5/bear=0 × 30%     │
    │  │                  + vol_bonus (hasta +0.1)             │
    │  ├─ macro_score     = fear_greed/100          × 25%      │
    │  ├─ news_score      = low=1.0/mod=0.65/...    × 15%      │
    │  └─ total           = suma ponderada (0.0–1.0)           │
    │                                                          │
    │  decision_engine.py                                      │
    │  ├─ Regla 1: total < MIN_CONFIDENCE → NO_SIGNAL          │
    │  ├─ Regla 2: consenso de señales (≥2/3 alineadas)        │
    │  │   ├─ ≥2 bullish  → APPROVE BUY                        │
    │  │   ├─ ≥2 bearish  → NO_SIGNAL (no hay short)           │
    │  │   └─ mixto       → NO_SIGNAL                          │
    │  └─ Tamaño dinámico:                                     │
    │      score ≥0.85 → size=0.15 (15% del portafolio)        │
    │      score ≥0.75 → size=0.10 (10%)                       │
    │      score ≥0.65 → size=0.05 (5%)                        │
    └────────┬─────────────────────────────────────────────────┘
             │
    ┌────────▼────────────────────────────────────────────────┐
    │                     SENDER LAYER                         │
    │                   (Capa de Envío)                        │
    │                                                          │
    │  signal_formatter.py                                     │
    │  ├─ APPROVE → payload status="pending"                   │
    │  │   strategy_id: "bot2_macro_research"                  │
    │  │   source: "bot2"                                      │
    │  │   research_summary: razón legible                     │
    │  │   score_breakdown: {sentiment, trend, macro, news}    │
    │  └─ NO_SIGNAL → payload status="no_signal" con reason    │
    │                                                          │
    │  webhook_client.py                                       │
    │  ├─ DRY_RUN=true  → solo loguea, no envía               │
    │  ├─ POST a http://127.0.0.1:8000/webhook/bot2            │
    │  │   Header: X-Webhook-Secret                            │
    │  ├─ backoff exponencial: 5s → 10s → 15s (3 intentos)    │
    │  ├─ status="executed"          → éxito, cooldown activo  │
    │  ├─ status="rejected"          → log + Telegram (no retry)│
    │  ├─ status="received_no_signal"→ confirmación OK         │
    │  └─ status="failed"            → pending_signals.json    │
    │                                                          │
    │  telegram_notifier.py                                    │
    │  ├─ signal_sent()     → ✅ señal aprobada y ejecutada    │
    │  ├─ signal_rejected() → ⚠️ rechazada por bot1            │
    │  ├─ webhook_failed()  → ❌ fallo de red, en cola         │
    │  └─ no_signal_cycle() → 🔍 ciclo sin señales + scores    │
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
│   Control de cooldown. Si elapsed < COOLDOWN_HOURS → símbolo saltado.
│   Solo se actualiza cuando bot1 confirma "executed".
│
├── pending_signals.json
│   [ { payload_spl }, { payload_qqq }, ... ]
│   Señales que fallaron por red (3 intentos agotados).
│   retry_pending() las reenvía al inicio del próximo ciclo.
│
└── decision_log.jsonl
    Una línea JSON por decisión. Append-only.
    Tipos: APPROVE | NO_SIGNAL | WEBHOOK_FAILED | REJECTED_BY_BOT1
```

---

## Reportes de Ciclo

```
logs/
└── YYYY-MM-DD_HH-MM-SS.json
    Reporte completo por cada ejecución:
    ├── cycle_id, started_at, finished_at, duration_seconds
    ├── mode (DRY_RUN / LIVE)
    ├── market_open (bool)
    ├── macro { fear_greed_score, vix, vix_regime, macro_bias }
    ├── symbols {
    │     SPY: { status, quote, headlines, sentiment, score, decision, webhook_response }
    │     QQQ: { ... }
    │   }
    └── summary { approved[], no_signal[], cooldown[], no_data[], webhook_failed[], rejected[] }
```

---

## Scheduler (APScheduler)

- **Trigger**: `interval` cada `CYCLE_INTERVAL_HOURS` horas (default: 4)
- **Timezone**: `America/New_York` (ET)
- **Ciclo inmediato**: Al arrancar, ejecuta un ciclo antes de programar el siguiente
- **Guard de mercado**: Fuera del horario 9:30–16:00 ET (lunes–viernes) → ciclo omitido, reporte escrito igual

---

## Fuentes de Datos

| Fuente | Módulo | API Key | Coste | Fallback |
|--------|--------|---------|-------|---------|
| Yahoo Finance (precios) | market_data.py | No | Gratis | `None` → símbolo saltado |
| Yahoo Finance (^VIX) | macro_indicators.py | No | Gratis | VIX = 20.0 |
| CNN Fear & Greed | macro_indicators.py | No | Gratis | score = 50.0 |
| NewsAPI | news_fetcher.py | Sí | Gratis (100/día) | Lista vacía → neutral |
| VADER NLP | sentiment_analyzer.py | No (local) | Gratis | neutral si 0 titulares |
| Telegram Bot API | telegram_notifier.py | Sí (opcional) | Gratis | No-op si vacío |

---

## Integración con bot1

| Campo | Valor |
|---|---|
| URL | `http://127.0.0.1:8000/webhook/bot2` |
| Header | `X-Webhook-Secret: {WEBHOOK_SECRET}` |
| `strategy_id` | `"bot2_macro_research"` |
| `params.source` | `"bot2"` |
| `params.research_summary` | Razón legible de la decisión |
| `params.score_breakdown` | `{sentiment, trend, macro, news}` — contribuciones ponderadas |

agente01 **no modifica bot1**. Se integra usando el contrato de webhook que bot1 ya tiene definido para el endpoint `/webhook/bot2`.
