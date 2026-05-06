# Flujo Completo — agente01 (SPY Specialist)

## Visión General

agente01 es un **especialista exclusivo en SPY**. Cada ciclo investiga SPY desde 6 dimensiones, aplica un pipeline de filtros en cascada, valida con Claude AI, y produce un resultado: `APPROVE` (swing long SPY con trailing stop) o `NO_SIGNAL` (informativo).

Adicionalmente, en cada ciclo **evalúa si la posición abierta SPY debe cerrarse** antes de que el trailing stop de Alpaca la cierre (invalidación de tesis).

---

## Ciclo Principal (`run_cycle`) — Flujo SPY Specialist

```
INICIO DEL CICLO (cada 60 min via APScheduler)
          │
          ▼
  ¿Mercado abierto? (lun–vie 9:30–16:00 ET)
          │ NO ──► Escribe reporte market_open=false → FIN
          │ SÍ
          ▼
  retry_pending()
  ← Reintenta señales fallidas de ciclos anteriores

  ┌── FASE 1: EXIT EVALUATOR (posicion SPY abierta si existe) ──────────────────┐
  │                                                                              │
  │  Si SPY tiene posición en open_positions.json:                              │
  │    Fetch precio + noticias + sentimiento frescos                             │
  │    Evalua 4 triggers:                                                        │
  │      T1: VIX > 30 (extremo)                → cierre forzado                │
  │      T2: trend=bearish AND vol_ratio > 1.5 → cierre forzado                │
  │      T3: compound < -0.5 AND >= 5 noticias → cierre forzado                │
  │      T4: elapsed_days >= max_holding_days  → cierre forzado                │
  │    Si trigger activo → POST close payload → bot1 → remove position          │
  │                                                                              │
  └──────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
  ¿SPY tiene posicion abierta?
          │ SÍ ──► HOLDING — log + Excel → FIN DEL ANÁLISIS SPY
          │ NO
          ▼

  ┌── FASE 2: SPY SPECIALIST (spy_cycle.run("SPY")) ───────────────────────────┐
  │                                                                              │
  │  ── 6 DIMENSIONES (cada una con fallback) ───────────────────────────────── │
  │                                                                              │
  │  1. Macro (25%)                                                              │
  │     FRED API: CPI, PCE, NFP, Fed Funds, yield curve                         │
  │     → macro_score 0.0–1.0                                                   │
  │                                                                              │
  │  2. Técnico (20%)                                                            │
  │     Yahoo Finance + Twelve Data 1D/4H/1H: RSI, MACD, BB, SMA200             │
  │     Ambas fuentes simultáneas; Yahoo preferido, TD cubre si Yahoo falla      │
  │     → technical_score 0.0–1.0 | bullish_count 0–3                           │
  │                                                                              │
  │  3. Componentes (20%)                                                        │
  │     Top-10 holdings + 11 sectores SPDR                                       │
  │     Yahoo batch primero; Twelve Data rellena símbolos no devueltos            │
  │     → components_score 0.0–1.0                                               │
  │                                                                              │
  │  4. Sentimiento (15%)                                                        │
  │     VIX term structure + Put/Call + Fear&Greed + VADER                       │
  │     → sentiment_score 0.0–1.0                                                │
  │                                                                              │
  │  5. Eventos (10%)                                                            │
  │     FOMC + Reuters RSS + economic calendar                                   │
  │     → events_score 0.0–1.0 | score_multiplier | veto                        │
  │                                                                              │
  │  6. Cross-Assets (10%)                                                       │
  │     DXY, TLT, HYG, QQQ, GLD, USO, BTC divergencias vs SPY                  │
  │     → cross_asset_score 0.0–1.0                                              │
  │                                                                              │
  │  ── PIPELINE DE FILTROS (filters.py) ───────────────────────────────────── │
  │                                                                              │
  │  PASO 1 — VETOS DUROS (→ NO_SIGNAL si alguno activo):                       │
  │    ✗ VIX > 30                           (pánico de mercado)                 │
  │    ✗ FOMC < 24h                         (Fed meeting próximo)               │
  │    ✗ ≥ 3 holdings top-10 con earnings < 48h                                 │
  │    ✗ RSI diario > 75                    (sobrecomprado)                     │
  │    ✗ SPY < SMA200                       (régimen bajista)                   │
  │    ✗ yield spread < -0.50% AND macro < 0.35 (macro invertida)              │
  │                                                                              │
  │  PASO 2 — SCORE COMPUESTO:                                                   │
  │    TOTAL = macro×0.25 + técnico×0.20 + componentes×0.20                     │
  │          + sentimiento×0.15 + eventos×0.10 + cross_assets×0.10              │
  │                                                                              │
  │  PASO 3 — MULTIPLICADOR DE EVENTOS:                                          │
  │    Evento EXTREME < 12h → veto directo                                      │
  │    Evento HIGH < 24h    → score × 0.85 (también trail × 0.70)              │
  │    Sin eventos          → × 1.0                                             │
  │                                                                              │
  │  PASO 4 — GATE DE APROBACIÓN:                                                │
  │    score × multiplicador >= 0.72                                             │
  │    AND dimensiones con score > 0.55  >=  5 de 6                             │
  │          │ FAIL ──► FilterResult(approved=False) → NO_SIGNAL                │
  │          │ PASS ──► FilterResult(approved=True)                             │
  │                                                                              │
  │  PASO 5 — VALIDACIÓN CLAUDE AI (claude_analyst.analyze):                    │
  │    Claude recibe: FilterResult + snapshot completo de mercado                │
  │    → Puede confirmar APPROVE (lo más frecuente)                             │
  │    → Puede vetar → override a NO_SIGNAL                                     │
  │    → Refina trail dentro del rango VIX permitido                            │
  │    (Claude NO puede promover NO_SIGNAL → APPROVE)                           │
  │                                                                              │
  └──────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
  RESULTADO: SpyCycleResult
    decision: "APPROVE" | "NO_SIGNAL"
    confidence: score final
    size: 0.08/0.12/0.18/0.25 (tier por score)
    trail_percent: 3.0/4.0/5.5 (por VIX régimen)
    vix_regime: low/moderate/high
    claude_reasoning: texto explicativo
    dimension_scores: {macro, technical, components, sentiment, events, cross_asset}
          │
          ▼ (si APPROVE)
  signal_formatter.build_spy_payload(result, vix_regime)
  strategy_id="bot2_swing_trailing" | source="bot2_spy_specialist"
  exit_strategy="trailing_stop" | claude_reasoning incluido
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
  FASE 3: PERSISTENCIA
    _write_cycle_report() → logs/YYYY-MM-DD_HH-MM-SS.json
    append_excel_rows()   → logs/trade_log.xlsx
    (ciclo SPY registrado con 6 dimensiones + claude_reasoning)
    FIN
```

---

## Las 6 Dimensiones y sus Pesos

| # | Dimensión | Peso | Fuente principal |
|---|-----------|------|-----------------|
| 1 | **Macro** | 25% | FRED API (CPI, PCE, NFP, yield curve) |
| 2 | **Técnico** | 20% | Yahoo Finance + Twelve Data multi-TF (1D/4H/1H): RSI, MACD, BB, SMA200 |
| 3 | **Componentes** | 20% | Yahoo Finance + Twelve Data — Top-10 holdings + 11 sectores SPDR |
| 4 | **Sentimiento** | 15% | VIX term structure + Put/Call + Fear&Greed + VADER |
| 5 | **Eventos** | 10% | FOMC + calendario + Reuters RSS geopolítica |
| 6 | **Cross-Assets** | 10% | Yahoo Finance + Twelve Data — DXY, TLT, HYG, QQQ, GLD, USO, BTC |

Para el detalle completo → ver [data_sources.md](data_sources.md).

---

## Fórmula del Score

```
TOTAL = (macro        × 0.25)
      + (técnico      × 0.20)
      + (componentes  × 0.20)
      + (sentimiento  × 0.15)
      + (eventos      × 0.10)
      + (cross_assets × 0.10)

SCORE_AJUSTADO = TOTAL × score_multiplier_eventos
```

---

## Vetos Duros (Paso 1)

| Veto | Condición | Efecto |
|---|---|---|
| VIX extremo | VIX > 30 | NO_SIGNAL inmediato |
| FOMC próximo | Fed meeting < 24h | NO_SIGNAL inmediato |
| Earnings top-10 | ≥ 3 holdings reportan en 48h | NO_SIGNAL inmediato |
| RSI sobrecomprado | RSI diario > 75 | NO_SIGNAL inmediato |
| Bajo SMA200 | Precio SPY < SMA200 | NO_SIGNAL inmediato |
| Macro invertida | Yield spread < -0.50% AND macro < 0.35 | NO_SIGNAL inmediato |

---

## Position Sizing — 4 Tiers

| Score total | Tamaño | Variable config |
|---|---|---|
| >= 0.90 | **25%** del capital | SIZE_TIER_1 |
| >= 0.82 | **18%** del capital | SIZE_TIER_2 |
| >= 0.75 | **12%** del capital | SIZE_TIER_3 |
| >= 0.72 | **8%** del capital | SIZE_TIER_4 |

---

## Trailing Stop por Régimen VIX

| Régimen | VIX | trail_percent | take_profit | max_holding_days |
|---|---|---|---|---|
| `low` | < 15 | 3.0% | null | 15 días |
| `moderate` | 15–25 | 4.0% | null | 10 días |
| `high` | 25–30 | 5.5% | 8.0% | 7 días |
| `extreme` | > 30 | — | — | No abrir |

Si hay evento HIGH < 24h: trail × 0.70 (más ajustado = más defensivo).

---

## Posibles Resultados en cada Ciclo

| Resultado | Condición | ¿Bot1 recibe? | Guardado en Excel |
|---|---|---|---|
| **APPROVE** | Filtros + gate + Claude confirman | ✅ Ejecuta buy + trailing | ✅ Fila completa con 6 dims |
| **NO_SIGNAL** | Filtros rechazan o Claude veta | ✅ Payload no_signal (informativo) | ✅ Fila completa |
| **HOLDING** | Posición SPY abierta — no se abre otra | ❌ No | ✅ Fila parcial |
| **EXIT_FORCED** | Trigger de cierre activado | ✅ Payload close (action="close") | ✅ Fila con motivo |
| **WEBHOOK_FAILED** | bot1 inaccesible tras 3 reintentos | ❌ No (reintenta al próximo ciclo) | ✅ Fila con error |
| **REJECTED_BY_BOT1** | bot1 responde `{"status":"rejected"}` | ❌ No (descartado) | ✅ Fila con estado |

**Todos los resultados se registran** en `decision_log.jsonl`, el reporte JSON del ciclo, y `trade_log.xlsx`.

---

## Persistencia y Resiliencia

| Archivo | Propósito |
|---|---|
| `state/last_signals.json` | Cooldown (SPY solo puede reentrar cuando no hay posición activa) |
| `state/open_positions.json` | Posición SPY activa — evita dobles entradas, habilita exit evaluator |
| `state/pending_signals.json` | Señales fallidas — se reintenta al inicio del próximo ciclo |
| `state/decision_log.jsonl` | Historial append-only de todas las decisiones |
| `logs/YYYY-MM-DD_HH-MM-SS.json` | Reporte completo de cada ciclo |
| `logs/trade_log.xlsx` | Registro Excel acumulativo — una fila por ciclo con 6 dimensiones |

---

## Comunicación con bot1

```
agente01 (127.0.0.1)
    │
    └──► POST http://127.0.0.1:8000/webhook/bot2
         Header: X-Webhook-Secret = WEBHOOK_SECRET
         Body (apertura): {
           strategy_id: "bot2_swing_trailing",
           source: "bot2_spy_specialist",
           action: "buy",
           trail_percent: 4.0,
           vix_regime_at_entry: "moderate",
           claude_reasoning: "...",
           score_breakdown: {macro, technical, components, sentiment, events, cross_asset}
         }
         Body (cierre): { action: "close", close_reason: "...", ... }
                    │
                    ▼
               bot1 → Alpaca Paper/Live API → Orden ejecutada
```

Ambos bots corren en la misma PC. La comunicación es directa via `127.0.0.1`.

---

## Horario de Operación (Lima, Perú — UTC-5)

| Periodo | Horario Lima | Nota |
|---|---|---|
| Durante EDT (Mar–Nov) | **08:30–15:00** | La mayoría del año |
| Durante EST (Nov–Mar) | **09:30–16:00** | Invierno USA |

**Ciclos prioritarios (hora Lima EDT):** 09:45 / 12:30 / 15:30
