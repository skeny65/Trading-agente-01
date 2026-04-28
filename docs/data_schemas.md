# Esquemas de Datos — agente01

Todos los archivos de estado viven en `state/`. Los reportes de ciclo en `logs/`. Ninguno se commitea (excluidos por `.gitignore`).

---

## Payload Webhook — Señal de Apertura (APPROVE BUY)

Enviado a `POST http://127.0.0.1:8000/webhook/bot2` cuando `decision=APPROVE`.

```json
{
  "timestamp": "2026-04-27T14:00:00.123456+00:00",
  "status": "pending",
  "processed": false,
  "signal": {
    "strategy_id": "bot2_swing_trailing",
    "symbol": "SPY",
    "action": "buy",
    "confidence": 0.813,
    "size": 0.05,
    "params": {
      "source": "bot2",
      "exit_strategy": "trailing_stop",
      "trail_percent": 4.0,
      "take_profit_pct": null,
      "max_holding_days": 10,
      "vix_regime_at_entry": "moderate",
      "research_summary": "Score 0.813 | 3/3 señales alcistas | trend=strong_bullish sentiment=positive macro=bullish",
      "score_breakdown": {
        "sentiment": 0.152,
        "trend":     0.400,
        "macro":     0.163,
        "vix":       0.098
      }
    }
  }
}
```

**Campos del signal:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `strategy_id` | str | Siempre `"bot2_swing_trailing"` |
| `symbol` | str | Símbolo en mayúsculas (ej: `"SPY"`) |
| `action` | str | `"buy"` (agente01 no hace short) |
| `confidence` | float | Score total (0.0–1.0) |
| `size` | float | Fracción de capital: 0.03, 0.05 o 0.08 |
| `params.source` | str | Siempre `"bot2"` |
| `params.exit_strategy` | str | Siempre `"trailing_stop"` |
| `params.trail_percent` | float | 3.0 (low) / 4.0 (moderate) / 5.5 (high) |
| `params.take_profit_pct` | float o null | null en low/moderate, 8.0 en high |
| `params.max_holding_days` | int | 15 (low) / 10 (moderate) / 7 (high) |
| `params.vix_regime_at_entry` | str | Régimen VIX al momento de apertura |
| `params.research_summary` | str | Razón legible de la decisión |
| `params.score_breakdown.sentiment` | float | Contribución del sentimiento (raw × 0.20) |
| `params.score_breakdown.trend` | float | Contribución de la tendencia (raw × 0.40) |
| `params.score_breakdown.macro` | float | Contribución del Fear & Greed (raw × 0.25) |
| `params.score_breakdown.vix` | float | Contribución del VIX (raw × 0.15) |

**Respuestas posibles de bot1:**

| HTTP | Body | Significado |
|---|---|---|
| 200 | `{"status":"executed","order_id":"..."}` | Orden ejecutada en Alpaca |
| 200 | `{"status":"rejected","reason":"..."}` | bot1 pausado por su manager |
| 401 | `{"detail":"unauthorized bot2 webhook"}` | WEBHOOK_SECRET incorrecto |

---

## Payload Webhook — Cierre Forzado (EXIT)

Enviado cuando `exit_evaluator` detecta que la tesis de una posición abierta ya no es válida.

```json
{
  "timestamp": "2026-04-28T11:30:00.123456+00:00",
  "status": "pending",
  "processed": false,
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

| Campo | Valor fijo | Significado |
|---|---|---|
| `action` | `"close"` | Cierra toda la posición |
| `confidence` | `1.0` | Cierre incondicional |
| `size` | `1.0` | Cierra el 100% de la posición |
| `close_reason` | texto | Trigger que activó el cierre |

**Posibles valores de `close_reason`:**
- `vix_spike_extreme: VIX=32.4`
- `trend_reversal_with_volume: trend=bearish, vol_ratio=1.8`
- `sentiment_crash: compound=-0.72, 6 headlines`
- `max_holding_reached: 10 days`

---

## Payload Webhook — Sin Señal (NO_SIGNAL)

Enviado a bot1 al final del ciclo cuando **ningún símbolo** supera el umbral. Bot1 lo registra en su log como información.

```json
{
  "timestamp": "2026-04-27T10:00:00.123456+00:00",
  "status": "no_signal",
  "processed": false,
  "reason": "Ningún simbolo supera umbral 0.70 [SPY:0.61 | QQQ:0.55 | IWM:0.48]",
  "signal": null
}
```

**Respuesta esperada de bot1:**
```json
{"status": "received_no_signal", "processed": true, "reason": "..."}
```

---

## state/open_positions.json

Seguimiento de posiciones activas. Evita dobles entradas y habilita el exit evaluator.

```json
{
  "SPY": {
    "opened_at": "2026-04-27T14:00:00+00:00",
    "vix_regime_at_entry": "moderate",
    "max_holding_days": 10,
    "action": "buy",
    "confidence": 0.813,
    "size": 0.05
  },
  "QQQ": {
    "opened_at": "2026-04-26T11:00:00+00:00",
    "vix_regime_at_entry": "low",
    "max_holding_days": 15,
    "action": "buy",
    "confidence": 0.851,
    "size": 0.08
  }
}
```

- **Se agrega** cuando bot1 confirma `"status": "executed"`
- **Se elimina** cuando se envía un cierre forzado exitoso
- Si el símbolo tiene entrada → el ciclo no abre otra (muestra `HOLDING`)

---

## state/last_signals.json

Control de cooldown. Registra cuándo se envió la última señal por símbolo.

```json
{
  "SPY": "2026-04-27T14:00:00.123456+00:00",
  "QQQ": "2026-04-26T11:00:00.456789+00:00"
}
```

- Se actualiza **solo** cuando bot1 confirma `"status":"executed"` (no en dry_run ni en rechazo).
- Si `now - last_signal < COOLDOWN_HOURS (24h)` → símbolo saltado.

---

## state/pending_signals.json

Cola de señales que no pudieron enviarse a bot1 por fallo de red (3 intentos agotados).

```json
[
  {
    "timestamp": "2026-04-27T14:00:00.123456+00:00",
    "status": "pending",
    "processed": false,
    "signal": {
      "strategy_id": "bot2_swing_trailing",
      "symbol": "SPY",
      "action": "buy",
      "confidence": 0.78,
      "size": 0.05,
      "params": {
        "source": "bot2",
        "exit_strategy": "trailing_stop",
        "trail_percent": 4.0,
        "take_profit_pct": null,
        "max_holding_days": 10,
        "vix_regime_at_entry": "moderate",
        "research_summary": "Score 0.780 | 3/3 señales alcistas",
        "score_breakdown": {
          "sentiment": 0.136,
          "trend":     0.400,
          "macro":     0.163,
          "vix":       0.098
        }
      }
    }
  }
]
```

- `retry_pending()` se llama al inicio de cada ciclo.
- Las enviadas con éxito se eliminan; las que siguen fallando permanecen.

---

## state/decision_log.jsonl

Historial completo de decisiones. Una entrada JSON por línea. Append-only. **Registra todos los eventos**, no solo los APPROVE.

**APPROVE (señal enviada y ejecutada):**
```json
{"ts":"2026-04-27T14:00:05+00:00","symbol":"SPY","decision":"APPROVE","action":"buy","confidence":0.813,"size":0.05,"reason":"Score 0.813 | 3/3 señales alcistas | trend=strong_bullish sentiment=positive macro=bullish","trail_config":{"trail_percent":4.0,"take_profit_pct":null,"max_holding_days":10},"vix_regime":"moderate","webhook_response":{"status":"executed","order_id":"a1b2c3d4-..."},"dry_run":false}
```

**NO_SIGNAL:**
```json
{"ts":"2026-04-27T10:00:00+00:00","symbol":"QQQ","decision":"NO_SIGNAL","reason":"Score 0.550 < umbral 0.70","score":0.55}
```

**EXIT_FORCED:**
```json
{"ts":"2026-04-28T11:30:00+00:00","symbol":"SPY","decision":"EXIT_FORCED","close_reason":"vix_spike_extreme: VIX=32.4","webhook_response":{"status":"executed"}}
```

**EXIT_CHECK_OK (posición vigente, no cerrar):**
```json
{"ts":"2026-04-28T10:00:00+00:00","symbol":"SPY","decision":"EXIT_CHECK_OK","reason":"Tesis valida — no se cierra"}
```

**HOLDING (nueva entrada bloqueada por posición abierta):**
```json
{"ts":"2026-04-28T10:00:00+00:00","symbol":"SPY","decision":"HOLDING","position":{"opened_at":"2026-04-27T14:00:00+00:00","vix_regime_at_entry":"moderate"}}
```

**COOLDOWN:**
```json
{"ts":"2026-04-28T10:00:00+00:00","symbol":"QQQ","decision":"COOLDOWN","cooldown_hours":24}
```

**WEBHOOK_FAILED:**
```json
{"ts":"2026-04-27T14:00:10+00:00","symbol":"SPY","decision":"WEBHOOK_FAILED","action":"buy","error":"Connection refused","score":0.813}
```

**REJECTED_BY_BOT1:**
```json
{"ts":"2026-04-27T14:00:08+00:00","symbol":"SPY","decision":"REJECTED_BY_BOT1","action":"buy","reason":"bot is paused by manager","score":0.813}
```

---

## logs/trade_log.xlsx

Registro Excel acumulativo. **Una fila por símbolo por ciclo**, sin importar el resultado.
Se crea automáticamente en `logs/trade_log.xlsx` al primer ciclo donde el mercado esté abierto.

**Estructura de columnas:**

| Columna | Tipo | Ejemplo |
|---|---|---|
| `timestamp_utc` | datetime | 2026-04-27T14:00:00+00:00 |
| `cycle_id` | str | 2026-04-27_14-00-00 |
| `mode` | str | DRY_RUN / LIVE |
| `priority_cycle` | bool | True |
| `symbol` | str | SPY |
| `status` | str | ANALYZED / HOLDING / COOLDOWN / EXIT_FORCED / ... |
| `decision` | str | APPROVE / NO_SIGNAL / HOLDING / EXIT_FORCED / ... |
| `action` | str | buy / close / none |
| `price` | float | 590.00 |
| `change_pct` | float | +1.19 |
| `sma20` | float | 572.00 |
| `sma50` | float | 555.00 |
| `trend_strength` | str | strong_bullish |
| `volume_ratio` | float | 1.42 |
| `sentiment_compound` | float | +0.52 |
| `sentiment_label` | str | positive |
| `fear_greed_score` | float | 65.0 |
| `fear_greed_label` | str | Greed |
| `vix` | float | 16.5 |
| `vix_regime` | str | moderate |
| `score_trend` | float | 1.00 |
| `score_sentiment` | float | 0.76 |
| `score_macro` | float | 0.65 |
| `score_vix` | float | 0.65 |
| `score_total` | float | 0.813 |
| `confidence` | float | 0.813 |
| `size` | float | 0.05 |
| `trail_percent` | float | 4.0 |
| `take_profit_pct` | float o vacío | (vacío si null) |
| `max_holding_days` | int | 10 |
| `reason` | str | Score 0.813 / 3/3 señales alcistas / ... |
| `webhook_status` | str | sent / dry_run / failed / rejected / n/a |

**Nota:** Si el archivo está abierto en Excel al momento en que el agente intenta escribir, aparecerá una advertencia en el log y los datos se omitirán para ese ciclo (sin crashear el agente). Cerrar el archivo permite que el próximo ciclo escriba normalmente.

---

## logs/YYYY-MM-DD_HH-MM-SS.json

Reporte completo de cada ciclo de ejecución.

```json
{
  "cycle_id": "2026-04-27_14-00-00",
  "started_at": "2026-04-27T14:00:00.000000+00:00",
  "finished_at": "2026-04-27T14:01:45.123456+00:00",
  "duration_seconds": 105.12,
  "mode": "LIVE",
  "priority_cycle": true,
  "market_open": true,
  "macro": {
    "fear_greed_score": 65.0,
    "fear_greed_label": "Greed",
    "vix": 16.5,
    "vix_regime": "moderate",
    "macro_bias": "bullish",
    "fetched_at": "2026-04-27T14:00:01.000000+00:00"
  },
  "symbols": {
    "SPY": {
      "status": "ANALYZED",
      "quote": {
        "price": 590.0,
        "prev_close": 583.0,
        "change_pct": 1.20,
        "volume": 85000000,
        "avg_volume": 60000000,
        "volume_ratio": 1.42,
        "sma20": 572.0,
        "sma50": 555.0,
        "price_vs_sma20": 3.15,
        "trend": "bullish",
        "trend_strength": "strong_bullish"
      },
      "headlines_count": 6,
      "headlines": [
        {"title": "Fed signals pause in rate hikes", "source": "Reuters", "published_at": "2026-04-27T13:45:00Z"},
        {"title": "SPY breaks key resistance level", "source": "MarketWatch", "published_at": "2026-04-27T13:30:00Z"}
      ],
      "sentiment": {
        "compound": 0.52,
        "label": "positive",
        "positive_ratio": 0.67,
        "negative_ratio": 0.08
      },
      "score": {
        "sentiment": 0.76,
        "trend": 1.0,
        "macro": 0.65,
        "vix": 0.65,
        "total": 0.813
      },
      "decision": {
        "verdict": "APPROVE",
        "action": "buy",
        "confidence": 0.813,
        "size": 0.05,
        "reason": "Score 0.813 | 3/3 señales alcistas | trend=strong_bullish sentiment=positive macro=bullish"
      },
      "trail_config": {
        "trail_percent": 4.0,
        "take_profit_pct": null,
        "max_holding_days": 10
      },
      "webhook_response": {
        "status": "executed",
        "order_id": "d43f5925-66bc-4227-81a6-7bb94faf3ab6"
      }
    },
    "QQQ": {
      "status": "COOLDOWN"
    },
    "IWM": {
      "status": "HOLDING",
      "position": {
        "opened_at": "2026-04-26T11:00:00+00:00",
        "vix_regime_at_entry": "low",
        "max_holding_days": 15,
        "action": "buy",
        "confidence": 0.851,
        "size": 0.08
      }
    }
  },
  "summary": {
    "approved":         ["SPY"],
    "exits":            [],
    "no_signal":        ["XLK", "XLF", "XLE", "XLV", "DIA"],
    "cooldown":         ["QQQ"],
    "holding":          ["IWM"],
    "no_data":          [],
    "webhook_failed":   [],
    "rejected_by_bot1": []
  }
}
```

**Valores posibles de `symbols[X].status`:**

| Status | Significado |
|---|---|
| `ANALYZED` | Ciclo completo — score + decisión calculados |
| `HOLDING` | Posición abierta — no se abre otra |
| `COOLDOWN` | Saltado por cooldown activo (24h) |
| `NO_DATA` | Sin datos de mercado (yfinance falló) |
