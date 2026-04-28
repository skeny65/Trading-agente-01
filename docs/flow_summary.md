# Flujo Completo — agente01

## Visión General

agente01 es un agente autónomo cuyo **único objetivo es investigar y decidir**. No ejecuta órdenes directamente. Cada ciclo consulta 5 fuentes de datos externas, combina la información en un score numérico, aplica reglas de consenso, y produce un único resultado: `APPROVE` (con payload de compra para bot1) o `NO_SIGNAL` (informativo).

---

## Ciclo Principal (`run_cycle`)

```
INICIO DEL CICLO (cada 4h via APScheduler)
          │
          ▼
  ¿Mercado abierto? (lun–vie 9:30–16:00 ET)
          │ NO ──▶ Escribe reporte market_open=false → FIN
          │ SÍ
          ▼
  retry_pending()
  ← Reintenta señales fallidas de ciclos anteriores
          │
          ▼
  ┌──────────────────────────────────────────────────┐
  │           INVESTIGACIÓN (por ciclo)              │
  │                                                  │
  │  Fuente 1: Yahoo Finance (^VIX)   → vix, régimen │
  │  Fuente 4: CNN Fear & Greed       → score 0–100  │
  │  → macro_bias: bullish/neutral/bearish           │
  │                                                  │
  │  Fuente 1: Yahoo Finance (precio) → por símbolo  │
  │  → precio, SMA20, volumen, trend                 │
  └──────────────────────────────────────────────────┘
          │
          ▼ (por cada símbolo en WATCHLIST)
  ┌──────────────────────────────────────────────────┐
  │           ANÁLISIS (por símbolo)                 │
  │                                                  │
  │  Fuente 2: NewsAPI  → titulares últimas 6h       │
  │  Fuente 3: VADER    → sentiment compound -1/+1   │
  │                                                  │
  │  Scorer:                                         │
  │    sentiment × 30%  +  trend × 30%               │
  │    + macro   × 25%  +  vix   × 15%               │
  │    = TOTAL (0.0–1.0)                             │
  └──────────────────────────────────────────────────┘
          │
          ▼
  ¿TOTAL ≥ MIN_CONFIDENCE (0.65)?
          │ NO ──▶ NO_SIGNAL → log → siguiente símbolo
          │ SÍ
          ▼
  ¿≥ 2/3 señales bullish?
  (trend + sentiment + macro_bias)
          │ NO ──▶ NO_SIGNAL → log → siguiente símbolo
          │ SÍ
          ▼
  signal_formatter.build_payload()
  strategy_id="bot2_macro_research" | source="bot2"
          │
          ▼
  webhook_client.send()
  POST http://127.0.0.1:8000/webhook/bot2
  Header: X-Webhook-Secret
          │
    ┌─────┴──────────┬────────────────┐
    ▼                ▼                ▼
 EJECUTADO       RECHAZADO        FALLO RED
 bot1 confirma   bot1 pausado     3 intentos
    │                │             fallidos
 cooldown        Telegram ⚠️    pending_signals.json
 Telegram ✅     log             Telegram ❌
 log             no reintenta    retry next cycle
          │
          ▼
  ¿Ningún símbolo aprobado?
          │ SÍ ──▶ Envía no_signal a bot1
          │        Telegram 🔍 con todos los scores
          ▼
  Escribe logs/YYYY-MM-DD_HH-MM-SS.json → FIN
```

---

## Las 5 Fuentes de Datos

| # | Fuente | Qué aporta | Peso |
|---|--------|-----------|------|
| 1 | Yahoo Finance (precio) | precio, SMA20, volumen, trend | 30% |
| 2 | NewsAPI.org | titulares últimas 6h | — |
| 3 | VADER NLP (local) | sentimiento de los titulares | 30% |
| 4 | CNN Fear & Greed | sentimiento macro del mercado | 25% |
| 5 | Yahoo Finance (^VIX) | volatilidad implícita | 15% |

Para el detalle completo → ver [data_sources.md](data_sources.md).

---

## Fórmula del Score

```
TOTAL = (sentiment_score × 0.30)
      + (trend_score     × 0.30)
      + (macro_score     × 0.25)
      + (news_score      × 0.15)

sentiment_score  =  (VADER_compound + 1) / 2
trend_score      =  bullish=1.0 / neutral=0.5 / bearish=0.0  + vol_bonus
macro_score      =  fear_greed_score / 100
news_score       =  VIX_low=1.0 / moderate=0.65 / high=0.30 / extreme=0.0
```

---

## Los 4 Posibles Resultados por Símbolo

| Resultado | Condición | ¿Bot1 recibe? |
|---|---|---|
| **APPROVE** | TOTAL ≥ MIN_CONFIDENCE + ≥2 señales bullish | ✅ Sí, ejecuta orden en Alpaca |
| **NO_SIGNAL** | score bajo, señales mixtas o bajistas | ✅ Sí, payload no_signal (informativo) |
| **WEBHOOK_FAILED** | bot1 inaccesible tras 3 reintentos | ❌ No (reintenta al próximo ciclo) |
| **REJECTED_BY_BOT1** | bot1 responde `{"status":"rejected"}` | ❌ No (descartado intencionalmente) |

---

## Tamaño de Posición

| Score | Size (fracción del portafolio) |
|---|---|
| ≥ 0.85 | 15% |
| ≥ 0.75 | 10% |
| ≥ 0.65 | 5% |

---

## Persistencia y Resiliencia

| Archivo | Propósito |
|---|---|
| `state/last_signals.json` | Cooldown por símbolo |
| `state/pending_signals.json` | Señales fallidas — se reintenta al inicio del próximo ciclo |
| `state/decision_log.jsonl` | Historial append-only de todas las decisiones |
| `logs/YYYY-MM-DD_HH-MM-SS.json` | Reporte completo de cada ciclo |

---

## Comunicación con bot1

```
agente01 (127.0.0.1)
    │
    └──► POST http://127.0.0.1:8000/webhook/bot2
         Header: X-Webhook-Secret = WEBHOOK_SECRET (mismo en ambos bots)
         Body: { strategy_id: "bot2_macro_research", source: "bot2", ... }
                        │
                        ▼
                   bot1 → Alpaca Paper/Live API → Orden ejecutada
```

Ambos bots corren en la misma PC. La comunicación es directa vía `127.0.0.1`, sin pasar por internet.
