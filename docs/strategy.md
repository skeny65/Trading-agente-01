# Estrategia — Swing Trading con Trailing Stop Dinámico

## Objetivo

agente01 opera bajo una estrategia de **swing trading** — posiciones de varios días que capturan movimientos de momentum sostenido. La salida ya no es un take-profit fijo: se usa un **trailing stop dinámico calibrado por el régimen de volatilidad (VIX)** en el momento de apertura.

El agente investiga, decide y envía la señal. bot1 y Alpaca manejan la ejecución y el trailing.

---

## Parámetros clave vs. versión anterior

| Parámetro | Anterior | Swing | Justificación |
|---|---|---|---|
| Frecuencia de ciclo | 4 horas | **60 minutos** | Capturar catalysts intradía sin caer en ruido |
| Umbral de score | 0.65 | **0.70** | Swing exige más calidad, menos trades |
| Consenso requerido | 2/3 señales | **3/3 señales** | Posiciones de días requieren máxima alineación |
| Cooldown por símbolo | 4 horas | **24 horas** | Un swing dura días, no se reabre en horas |
| Take profit | 4% fijo | **Trailing dinámico** | Deja correr ganancias, respeta volatilidad |
| Stop loss | 2% fijo | **Reemplazado por trailing** | El trailing actúa como stop dinámico |
| Sizes de posición | 5% / 10% / 15% | **3% / 5% / 8%** | Más diversificación, hasta 12 posiciones |
| Ventana de noticias | 6 horas | **4 horas** | Alineada al ciclo de 1h |
| Peso trend en score | 30% | **40%** | La tendencia pesa más en swing |
| Peso sentiment | 30% | **20%** | Menos dependencia de noticias cortas |
| Watchlist | SPY, QQQ | **8 ETFs** | SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV |

---

## Trailing Stop Dinámico por Régimen VIX

El parámetro `trail_percent` que recibe bot1 no es fijo. Se calcula en el momento de apertura según el VIX actual:

| Régimen VIX | VIX | trail_percent | take_profit | max_holding_days |
|---|---|---|---|---|
| `low` | < 15 | **3.0%** | null (sin TP, dejar correr) | 15 días |
| `moderate` | 15–20 | **4.0%** | null | 10 días |
| `high` | 20–30 | **5.5%** | **8.0%** (defensivo) | 7 días |
| `extreme` | > 30 | — | — | **No abrir** |

**Razón**: un trailing del 3% con VIX en 25 te saca con cualquier vela normal. La volatilidad dicta el espacio que necesita el trade para respirar.

---

## Ciclos Prioritarios

Tres ciclos del día se marcan como `[PRIORITY]` en los logs porque coinciden con momentos clave del mercado:

| Hora ET | Razón |
|---|---|
| **09:45** | Post-apertura — mercado asentado tras los primeros 15 min de alta volatilidad |
| **12:30** | Media sesión — sesión europea cerrada, momentum USA puro |
| **15:30** | Pre-cierre — última decisión sobre exposición overnight |

---

## Scoring Recalibrado

```
TOTAL = (trend × 40%) + (sentiment × 20%) + (macro × 25%) + (vix × 15%)
```

La tendencia pesa más porque en swing trading la dirección del precio es el factor dominante. El sentimiento de noticias de corto plazo baja de peso.

**Lógica de trend_strength** (usa SMA20 y SMA50):

| trend_strength | Condición | Score |
|---|---|---|
| `strong_bullish` | precio > SMA20 > SMA50 | 1.00 |
| `bullish` | precio > SMA20, SMA20 ≈ SMA50 | 0.75 |
| `neutral` | precio ≈ SMA20 | 0.50 |
| `bearish` | precio < SMA20 | 0.25 |
| `strong_bearish` | precio < SMA20 < SMA50 | 0.00 |

---

## Motor de Decisión Actualizado

**Regla 0** (nueva): Si `vix_regime == "extreme"` → `NO_SIGNAL` inmediato, no se abren posiciones.

**Regla 1**: `score.total < 0.70` → `NO_SIGNAL`

**Regla 2**: Consenso **3/3** (todas las señales deben apuntar a bullish):
- `trend == "bullish"` ✓
- `sentiment.label == "positive"` ✓
- `macro_bias == "bullish"` ✓

Si las 3 se cumplen → `APPROVE BUY`

**Tamaño dinámico**:
```
score ≥ 0.85  →  size = 8%
score ≥ 0.78  →  size = 5%
score ≥ 0.70  →  size = 3%
```

---

## Invalidación de Tesis (exit_evaluator.py)

En cada ciclo, el agente evalúa si una posición abierta debe cerrarse **antes de que el trailing de Alpaca se active**. Hay 4 triggers:

| # | Trigger | Condición | Señal enviada |
|---|---|---|---|
| 1 | VIX spike extremo | `vix_regime == "extreme"` | `action: "close"`, reason: `vix_spike_extreme` |
| 2 | Reversión con volumen | `trend == "bearish"` + `volume_ratio > 1.5` | `action: "close"`, reason: `trend_reversal_with_volume` |
| 3 | Crash de sentimiento | `compound < -0.5` + `≥ 5 titulares` | `action: "close"`, reason: `sentiment_crash` |
| 4 | Tiempo máximo | `elapsed_days >= max_holding_days` del régimen VIX de apertura | `action: "close"`, reason: `max_holding_reached` |

El payload de cierre:
```json
{
  "status": "pending",
  "signal": {
    "strategy_id": "bot2_swing_trailing",
    "symbol": "SPY",
    "action": "close",
    "confidence": 1.0,
    "size": 1.0,
    "params": {
      "source": "bot2",
      "close_reason": "vix_spike_extreme: VIX=32.4",
      "research_summary": "Cierre forzado: vix_spike_extreme: VIX=32.4"
    }
  }
}
```

---

## Payload de Apertura (APPROVE BUY)

```json
{
  "status": "pending",
  "signal": {
    "strategy_id": "bot2_swing_trailing",
    "symbol": "SPY",
    "action": "buy",
    "confidence": 0.782,
    "size": 0.05,
    "params": {
      "source": "bot2",
      "exit_strategy": "trailing_stop",
      "trail_percent": 4.0,
      "take_profit_pct": null,
      "max_holding_days": 10,
      "vix_regime_at_entry": "moderate",
      "research_summary": "Score 0.782 | 3/3 señales alcistas | trend=strong_bullish sentiment=positive macro=bullish",
      "score_breakdown": {
        "sentiment": 0.168,
        "trend":     0.300,
        "macro":     0.180,
        "news":      0.098
      }
    }
  }
}
```

---

## Seguimiento de Posiciones Abiertas

El agente mantiene `state/open_positions.json` para saber qué posiciones están activas:

```json
{
  "SPY": {
    "opened_at":           "2026-04-28T14:00:00Z",
    "vix_regime_at_entry": "moderate",
    "max_holding_days":    10,
    "action":              "buy",
    "confidence":          0.782,
    "size":                0.05
  }
}
```

- Se agrega cuando bot1 confirma `"status": "executed"`
- Se elimina cuando se envía un cierre forzado exitoso
- Si el símbolo tiene posición abierta → el ciclo no abre otra entrada

---

## Watchlist Recomendada

ETFs de índice y sectoriales — alta liquidez, spreads mínimos, óptimos para swing:

| ETF | Índice / Sector |
|---|---|
| SPY | S&P 500 |
| QQQ | Nasdaq 100 |
| IWM | Russell 2000 (small caps) |
| DIA | Dow Jones |
| XLK | Tecnología |
| XLF | Financieras |
| XLE | Energía |
| XLV | Salud |
