# Estrategia — SPY Specialist: Swing Trading con Trailing Stop Dinámico

## Objetivo

agente01 es un **especialista en SPY** (S&P 500 ETF). Investiga el mercado desde 6 dimensiones, aplica un pipeline de filtros en cascada, y usa Claude AI como motor de decisión final. El resultado es siempre binario: `APPROVE` (swing long SPY) o `NO_SIGNAL`.

El agente investiga y decide. bot1 y Alpaca manejan la ejecución y el trailing stop.

---

## Cambios vs. arquitectura legacy

| Parámetro | Legacy multi-símbolo | SPY Specialist | Justificación |
|---|---|---|---|
| Símbolos | 8 ETFs (SPY, QQQ, IWM...) | **SPY únicamente** | Especialización profunda en un solo activo |
| Dimensiones de análisis | 4 componentes | **6 dimensiones** | Macro FRED, técnico multi-TF, componentes, sentimiento, eventos, cross-assets |
| Umbral de score | 0.70 | **0.72** | Mayor exigencia en el especialista |
| Dimensiones mínimas | — | **5 de 6 > 0.55** | Gate adicional de calidad |
| Motor de decisión | Reglas hardcoded | **Claude AI (Haiku)** | Validación narrativa + doble check |
| Sizing | 3% / 5% / 8% | **8% / 12% / 18% / 25%** | 4 tiers calibrados al score SPY |
| Fuentes de datos | 5 | **12+** | FRED API, CBOE, Trading Economics, fed.gov, Reuters RSS... |

---

## Las 6 Dimensiones

| # | Dimensión | Peso | Fuente principal |
|---|-----------|------|-----------------|
| 1 | **Macro** | 25% | FRED API (CPI, PCE, NFP, Fed Funds Rate, yield curve) |
| 2 | **Técnico** | 20% | yfinance multi-timeframe (1D / 4H / 1H): RSI, MACD, BB, SMA200 |
| 3 | **Componentes** | 20% | Top-10 holdings SPY + 11 sectores SPDR |
| 4 | **Sentimiento** | 15% | VIX term structure + Put/Call CBOE + Fear&Greed + VADER |
| 5 | **Eventos** | 10% | FOMC + calendario económico + geopolítica |
| 6 | **Cross-Assets** | 10% | DXY, TLT, HYG, QQQ, GLD, USO, BTC divergencias vs SPY |

**Fórmula del score total:**
```
TOTAL = macro×0.25 + técnico×0.20 + componentes×0.20
      + sentimiento×0.15 + eventos×0.10 + cross_assets×0.10
```

---

## Pipeline de Filtros en Cascada

### Paso 1 — Vetos Duros (→ NO_SIGNAL inmediato si alguno activo)

| Veto | Condición |
|------|-----------|
| VIX extremo | VIX > 30 (pánico de mercado) |
| FOMC próximo | Reunión Fed en < 24 horas |
| Earnings top-10 | ≥ 3 holdings del top-10 SPY reportan en 48h |
| RSI sobrecomprado | RSI diario > 75 |
| Bajo SMA200 | Precio SPY < SMA200 diaria (régimen bajista) |
| Macro invertida | Yield curve spread < -0.50% AND macro_score < 0.35 |

### Paso 2 — Score compuesto

Suma ponderada de las 6 dimensiones (0.0–1.0).

### Paso 3 — Filtros suaves (multiplicadores)

| Evento | Multiplicador de score |
|--------|----------------------|
| Evento EXTREME < 12h | veto directo |
| Evento HIGH < 24h | × 0.85 (también ajusta trail -30%) |
| Sin eventos | × 1.0 |

### Paso 4 — Gate de aprobación

```
score × multiplicador >= 0.72
AND
dimensiones con score > 0.55  >=  5 de 6
```

### Paso 5 — Validación Claude AI

Claude recibe el resultado del filtro + snapshot de mercado y puede:
- Confirmar APPROVE (lo más frecuente si el filtro pasó)
- Vetar la señal (override a NO_SIGNAL si detecta inconsistencias narrativas)
- Refinar el tamaño/trail dentro del rango permitido

---

## Trailing Stop Dinámico por Régimen VIX

| Régimen VIX | VIX | trail_percent | take_profit | max_holding_days |
|---|---|---|---|---|
| `low` | < 15 | **3.0%** | null (sin TP, dejar correr) | 15 días |
| `moderate` | 15–25 | **4.0%** | null | 10 días |
| `high` | 25–30 | **5.5%** | **8.0%** (defensivo) | 7 días |
| `extreme` | > 30 | — | — | **No abrir** |

Si hay evento de alto impacto < 24h: trail se ajusta × 0.70 (más ajustado = más defensivo).

---

## Position Sizing — 4 Tiers por Score

| Score total | Tamaño | Variable config |
|---|---|---|
| >= 0.90 | **25%** del capital | SIZE_TIER_1 |
| >= 0.82 | **18%** del capital | SIZE_TIER_2 |
| >= 0.75 | **12%** del capital | SIZE_TIER_3 |
| >= 0.72 | **8%** del capital | SIZE_TIER_4 |

---

## Ciclos Prioritarios

| Hora ET | Razón |
|---|---|
| **09:45** | Post-apertura — mercado asentado tras los primeros 15 min |
| **12:30** | Media sesión — sesión europea cerrada, momentum USA puro |
| **15:30** | Pre-cierre — última decisión sobre exposición overnight |

Marcados como `[PRIORITY]` en los logs.

---

## Payload de Apertura — SPY Specialist (APPROVE BUY)

```json
{
  "status": "pending",
  "signal": {
    "strategy_id": "bot2_swing_trailing",
    "symbol": "SPY",
    "action": "buy",
    "confidence": 0.748,
    "size": 0.12,
    "params": {
      "source": "bot2_spy_specialist",
      "exit_strategy": "trailing_stop",
      "trail_percent": 4.0,
      "take_profit_pct": null,
      "max_holding_days": 10,
      "vix_regime_at_entry": "moderate",
      "research_summary": "Score 0.748 | 5/6 dimensiones > 0.55 | size=12% | trail=4.0%",
      "claude_reasoning": "Technical and cross-asset dimensions show bullish alignment with SPY above SMA200 and QQQ leading. Macro headwinds from elevated CPI remain a drag on the composite score. Approving with conservative sizing given 5/6 dimensions passing.",
      "score_breakdown": {
        "macro":       0.512,
        "technical":   0.810,
        "components":  0.740,
        "sentiment":   0.630,
        "events":      0.700,
        "cross_asset": 0.680
      }
    }
  }
}
```

---

## Invalidación de Tesis (exit_evaluator.py)

Los 4 triggers de cierre forzado no cambiaron con la migración SPY Specialist:

| # | Trigger | Condición |
|---|---------|-----------|
| 1 | VIX spike extremo | `vix_regime == "extreme"` |
| 2 | Reversión con volumen | `trend == "bearish"` AND `volume_ratio > 1.5` |
| 3 | Crash de sentimiento | `compound < -0.5` AND `headline_count >= 5` |
| 4 | Tiempo máximo | `elapsed_days >= max_holding_days` del régimen VIX de apertura |

---

## Seguimiento de Posiciones

`state/open_positions.json` — evita dobles entradas y habilita exit_evaluator:

```json
{
  "SPY": {
    "opened_at":           "2026-04-28T14:00:00Z",
    "vix_regime_at_entry": "moderate",
    "max_holding_days":    10,
    "action":              "buy",
    "confidence":          0.748,
    "size":                0.12
  }
}
```

- Se agrega cuando bot1 confirma `"status": "executed"`
- Se elimina cuando se envía un cierre forzado exitoso
- Si SPY tiene posición abierta → el ciclo lo salta (HOLDING) y no abre otra
