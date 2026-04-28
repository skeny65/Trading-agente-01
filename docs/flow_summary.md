# Flujo Completo — agente01

## Visión General

agente01 es un agente autónomo cuyo **único objetivo es investigar y decidir**. No ejecuta órdenes directamente. Cada ciclo consulta 5 fuentes de datos externas, combina la información en un score numérico, aplica reglas de consenso, y produce un resultado: `APPROVE` (señal de compra con trailing stop) o `NO_SIGNAL` (informativo).

Adicionalmente, en cada ciclo **evalúa si las posiciones abiertas deben cerrarse** antes de que el trailing stop de Alpaca las cierre (invalidación de tesis).

---

## Ciclo Principal (`run_cycle`)

```
INICIO DEL CICLO (cada 60 min via APScheduler)
          │
          ▼
  ¿Mercado abierto? (lun–vie 9:30–16:00 ET / 08:30–15:00 Lima)
          │ NO ──► Escribe reporte market_open=false → FIN
          │ SÍ
          ▼
  retry_pending()
  ← Reintenta señales fallidas de ciclos anteriores

  ┌── FASE 1: EXIT EVALUATOR (por cada posicion en open_positions.json) ──┐
  │                                                                        │
  │  Para cada posicion abierta:                                           │
  │    Fetch precio + noticias + sentimiento frescos                       │
  │    Evalua 4 triggers:                                                  │
  │      T1: VIX > 30 (extremo)          → cierre forzado                │
  │      T2: trend=bearish + vol_ratio>1.5 → cierre forzado              │
  │      T3: compound < -0.5 + >= 5 noticias → cierre forzado            │
  │      T4: elapsed_days >= max_holding_days → cierre forzado            │
  │    Si trigger activo → POST close payload → bot1 → remove position    │
  │                                                                        │
  └────────────────────────────────────────────────────────────────────────┘
          │
          ▼
  ┌──────────────────────────────────────────────────────────┐
  │           INVESTIGACIÓN MACRO (una vez por ciclo)        │
  │                                                          │
  │  Fuente 4: CNN Fear & Greed  → score 0–100, macro_bias   │
  │  Fuente 5: Yahoo ^VIX        → vix, vix_regime           │
  │  Fuente 1: Yahoo Finance     → precios de todo WATCHLIST │
  │             precio, SMA20, SMA50, trend_strength         │
  └──────────────────────────────────────────────────────────┘
          │
          ▼ (por cada símbolo en WATCHLIST)
  ┌──────────────────────────────────────────────────────────┐
  │           FASE 2: ANÁLISIS (por símbolo)                 │
  │                                                          │
  │  ¿Tiene posicion abierta? → HOLDING (skip)               │
  │  ¿En cooldown (24h)?      → COOLDOWN (skip)              │
  │  ¿Sin datos de precio?    → NO_DATA (skip)               │
  │                                                          │
  │  Fuente 2: NewsAPI   → titulares ultimas 4h              │
  │  Fuente 3: VADER     → sentiment compound -1/+1          │
  │                                                          │
  │  Scorer (pesos: trend 40% | sentiment 20% | macro 25% | vix 15%):
  │    trend_score     = strength_map[trend_strength] + vol_bonus
  │    sentiment_score = (compound + 1) / 2
  │    macro_score     = fear_greed_score / 100
  │    vix_score       = low=1.0/mod=0.65/high=0.30/ext=0.0
  │    TOTAL = suma ponderada
  └──────────────────────────────────────────────────────────┘
          │
          ▼
  ¿VIX regime == "extreme"?
          │ SÍ ──► NO_SIGNAL (Regla 0)
          │ NO
          ▼
  ¿TOTAL >= MIN_CONFIDENCE (0.70)?
          │ NO ──► NO_SIGNAL → log + Excel → siguiente símbolo
          │ SÍ
          ▼
  ¿3/3 señales bullish?
  (trend=="bullish" + sentiment=="positive" + macro=="bullish")
          │ NO ──► NO_SIGNAL → log + Excel → siguiente símbolo
          │ SÍ
          ▼
  get_trail_config(vix_regime)
  → trail_percent (3.0/4.0/5.5%) + take_profit + max_holding_days

  signal_formatter.build_payload()
  strategy_id="bot2_swing_trailing" | source="bot2"
  exit_strategy="trailing_stop"
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
 cooldown        Telegram ⚠️   pending_signals.json
 open_position   log            Telegram ❌
 Telegram ✅     no reintenta   retry next cycle
 log
          │
          ▼
  ¿Ningún símbolo aprobado?
          │ SÍ ──► Envía no_signal a bot1
          │        Telegram 🔍 con todos los scores
          ▼
  FASE 3: PERSISTENCIA
    _write_cycle_report() → logs/YYYY-MM-DD_HH-MM-SS.json
    append_excel_rows()   → logs/trade_log.xlsx
    (todos los símbolos del ciclo quedan registrados)
    FIN
```

---

## Las 5 Fuentes de Datos

| # | Fuente | Qué aporta | Peso |
|---|--------|-----------|------|
| 1 | Yahoo Finance (precio, 60d) | precio, SMA20, SMA50, trend_strength | 40% |
| 2 | NewsAPI.org | titulares ultimas 4h | — |
| 3 | VADER NLP (local) | sentimiento de los titulares | 20% |
| 4 | CNN Fear & Greed | sentimiento macro del mercado | 25% |
| 5 | Yahoo Finance (^VIX) | volatilidad implícita + trailing config | 15% |

Para el detalle completo → ver [data_sources.md](data_sources.md).

---

## Fórmula del Score

```
TOTAL = (trend_score     × 0.40)
      + (sentiment_score × 0.20)
      + (macro_score     × 0.25)
      + (vix_score       × 0.15)

trend_score      =  strength_map[trend_strength] + vol_bonus
                    strong_bullish=1.0 / bullish=0.75 / neutral=0.50
                    bearish=0.25 / strong_bearish=0.00
sentiment_score  =  (VADER_compound + 1) / 2
macro_score      =  fear_greed_score / 100
vix_score        =  low=1.0 / moderate=0.65 / high=0.30 / extreme=0.0
```

---

## Posibles resultados por símbolo en cada ciclo

| Resultado | Condición | ¿Bot1 recibe? | Guardado en Excel |
|---|---|---|---|
| **APPROVE** | score >= 0.70 + 3/3 bullish + VIX != extreme | ✅ Ejecuta orden + trailing stop | ✅ Fila completa |
| **NO_SIGNAL** | score bajo, señales mixtas, VIX extremo | ✅ Payload no_signal (informativo) | ✅ Fila completa |
| **HOLDING** | Posición abierta — no se abre otra | ❌ No | ✅ Fila parcial |
| **COOLDOWN** | Señal enviada hace < 24h | ❌ No | ✅ Fila parcial |
| **NO_DATA** | yfinance no devolvió datos | ❌ No | ✅ Fila parcial |
| **EXIT_FORCED** | Trigger de cierre activado | ✅ Payload close (action="close") | ✅ Fila con motivo |
| **WEBHOOK_FAILED** | Bot1 inaccesible tras 3 reintentos | ❌ No (reintenta al próximo ciclo) | ✅ Fila con error |
| **REJECTED_BY_BOT1** | Bot1 responde `{"status":"rejected"}` | ❌ No (descartado) | ✅ Fila con estado |

**Todos los resultados se registran** en `decision_log.jsonl`, el reporte JSON del ciclo, y `trade_log.xlsx`.

---

## Trailing Stop Dinámico por Régimen VIX

| Régimen | VIX | trail_percent | take_profit | max_holding_days |
|---|---|---|---|---|
| `low` | < 15 | 3.0% | null | 15 días |
| `moderate` | 15–20 | 4.0% | null | 10 días |
| `high` | 20–30 | 5.5% | 8.0% | 7 días |
| `extreme` | > 30 | — | — | No abrir |

---

## Persistencia y Resiliencia

| Archivo | Propósito |
|---|---|
| `state/last_signals.json` | Cooldown 24h por símbolo |
| `state/open_positions.json` | Posiciones activas — evita dobles entradas, habilita exit evaluator |
| `state/pending_signals.json` | Señales fallidas — se reintenta al inicio del próximo ciclo |
| `state/decision_log.jsonl` | Historial append-only de todas las decisiones |
| `logs/YYYY-MM-DD_HH-MM-SS.json` | Reporte completo de cada ciclo |
| `logs/trade_log.xlsx` | Registro Excel acumulativo — una fila por símbolo por ciclo |

---

## Comunicación con bot1

```
agente01 (127.0.0.1)
    │
    └──► POST http://127.0.0.1:8000/webhook/bot2
         Header: X-Webhook-Secret = WEBHOOK_SECRET (mismo en ambos bots)
         Body (apertura): { strategy_id: "bot2_swing_trailing", action: "buy",
                            trail_percent: 4.0, vix_regime_at_entry: "moderate", ... }
         Body (cierre):   { strategy_id: "bot2_swing_trailing", action: "close",
                            close_reason: "vix_spike_extreme: VIX=32.4", ... }
                        │
                        ▼
                   bot1 → Alpaca Paper/Live API → Orden ejecutada
```

Ambos bots corren en la misma PC. La comunicación es directa via `127.0.0.1`, sin pasar por internet.

---

## Horario de Operación (Lima, Perú — UTC-5)

El agente corre 24/7 pero solo analiza cuando el mercado NYSE/NASDAQ está abierto.

| Periodo | Horario Lima | Nota |
|---|---|---|
| Durante EDT (Mar–Nov) | **08:30–15:00** | La mayoría del año |
| Durante EST (Nov–Mar) | **09:30–16:00** | Invierno USA |

El scheduler usa `America/New_York` — el cambio de horario se maneja automáticamente.

**Ciclos prioritarios en hora Lima (EDT):** 09:45 / 12:30 / 15:30
