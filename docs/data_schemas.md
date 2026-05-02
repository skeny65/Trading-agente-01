# Esquemas de Datos — agente01 (SPY Specialist)

Todos los archivos de estado viven en `state/`. Los reportes de ciclo en `logs/`. Ninguno se commitea (excluidos por `.gitignore`).

---

## Payload Webhook — Señal de Apertura SPY (APPROVE BUY)

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
      "claude_reasoning": "Technical and cross-asset dimensions show bullish alignment with SPY above SMA200 and QQQ leading. Macro headwinds from elevated CPI remain a drag. Approving with conservative sizing given 5/6 dimensions passing.",
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

**Campos del signal:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `strategy_id` | str | Siempre `"bot2_swing_trailing"` |
| `symbol` | str | Siempre `"SPY"` |
| `action` | str | `"buy"` (agente01 no hace short) |
| `confidence` | float | Score total ajustado (0.72–1.0 en APPROVE) |
| `size` | float | Fracción de capital: 0.08 / 0.12 / 0.18 / 0.25 |
| `params.source` | str | Siempre `"bot2_spy_specialist"` |
| `params.exit_strategy` | str | Siempre `"trailing_stop"` |
| `params.trail_percent` | float | 3.0 (low) / 4.0 (moderate) / 5.5 (high) |
| `params.take_profit_pct` | float o null | null en low/moderate, 8.0 en high |
| `params.max_holding_days` | int | 15 (low) / 10 (moderate) / 7 (high) |
| `params.vix_regime_at_entry` | str | Régimen VIX al momento de apertura |
| `params.research_summary` | str | Razón legible de la decisión |
| `params.claude_reasoning` | str | Razonamiento narrativo de Claude AI |
| `params.score_breakdown.macro` | float | Score dimensión 1 (0.0–1.0) |
| `params.score_breakdown.technical` | float | Score dimensión 2 (0.0–1.0) |
| `params.score_breakdown.components` | float | Score dimensión 3 (0.0–1.0) |
| `params.score_breakdown.sentiment` | float | Score dimensión 4 (0.0–1.0) |
| `params.score_breakdown.events` | float | Score dimensión 5 (0.0–1.0) |
| `params.score_breakdown.cross_asset` | float | Score dimensión 6 (0.0–1.0) |

**Respuestas posibles de bot1:**

| HTTP | Body | Significado |
|---|---|---|
| 200 | `{"status":"executed","order_id":"..."}` | Orden ejecutada en Alpaca |
| 200 | `{"status":"rejected","reason":"..."}` | bot1 pausado por su manager |
| 401 | `{"detail":"unauthorized bot2 webhook"}` | WEBHOOK_SECRET incorrecto |

---

## Payload Webhook — Cierre Forzado (EXIT)

Enviado cuando `exit_evaluator` detecta que la tesis de la posición abierta SPY ya no es válida.

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
      "source": "bot2_spy_specialist",
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

Enviado a bot1 al final del ciclo cuando SPY no supera el umbral o Claude veta. Bot1 lo registra como información.

```json
{
  "timestamp": "2026-04-27T10:00:00.123456+00:00",
  "status": "no_signal",
  "processed": false,
  "reason": "Score 0.61 < umbral 0.72 [SPY: macro=0.42 técnico=0.55 sentimiento=0.60]",
  "signal": null
}
```

**Respuesta esperada de bot1:**
```json
{"status": "received_no_signal", "processed": true, "reason": "..."}
```

---

## state/open_positions.json

Seguimiento de la posición SPY activa. Evita dobles entradas y habilita el exit evaluator.

```json
{
  "SPY": {
    "opened_at":           "2026-04-27T14:00:00+00:00",
    "vix_regime_at_entry": "moderate",
    "max_holding_days":    10,
    "action":              "buy",
    "confidence":          0.748,
    "size":                0.12
  }
}
```

- **Se agrega** cuando bot1 confirma `"status": "executed"`
- **Se elimina** cuando se envía un cierre forzado exitoso
- Si SPY tiene entrada → el ciclo lo salta (HOLDING) y no abre otra

---

## state/last_signals.json

Control de cooldown. Registra cuándo se envió la última señal.

```json
{
  "SPY": "2026-04-27T14:00:00.123456+00:00"
}
```

- Se actualiza **solo** cuando bot1 confirma `"status":"executed"` (no en dry_run ni en rechazo).
- El cooldown para SPY es gestionado principalmente por `open_positions.json` (no se reabre hasta que la posición se cierra).

---

## state/pending_signals.json

Cola de señales que no pudieron enviarse a bot1 por fallo de red.

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
        "claude_reasoning": "Bullish alignment across technical and cross-asset. Approving.",
        "score_breakdown": {
          "macro": 0.512, "technical": 0.810, "components": 0.740,
          "sentiment": 0.630, "events": 0.700, "cross_asset": 0.680
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

Historial completo de decisiones. Una entrada JSON por línea. Append-only.

**APPROVE (señal enviada y ejecutada):**
```json
{"ts":"2026-04-27T14:00:05+00:00","symbol":"SPY","decision":"APPROVE","action":"buy","confidence":0.748,"size":0.12,"reason":"Score 0.748 | 5/6 dimensiones > 0.55 | size=12% | trail=4.0%","claude_reasoning":"Technical and cross-asset show bullish alignment...","trail_config":{"trail_percent":4.0,"take_profit_pct":null,"max_holding_days":10},"vix_regime":"moderate","dimension_scores":{"macro":0.512,"technical":0.810,"components":0.740,"sentiment":0.630,"events":0.700,"cross_asset":0.680},"webhook_response":{"status":"executed","order_id":"a1b2c3d4-..."},"dry_run":false}
```

**NO_SIGNAL (veto duro):**
```json
{"ts":"2026-04-27T10:00:00+00:00","symbol":"SPY","decision":"NO_SIGNAL","reason":"veto_duro: RSI diario > 75 (sobrecomprado)"}
```

**NO_SIGNAL (score bajo):**
```json
{"ts":"2026-04-27T10:00:00+00:00","symbol":"SPY","decision":"NO_SIGNAL","reason":"Score 0.61 < umbral 0.72","confidence":0.61,"dimensions_passing":4}
```

**NO_SIGNAL (Claude veto):**
```json
{"ts":"2026-04-27T10:00:00+00:00","symbol":"SPY","decision":"NO_SIGNAL","reason":"Claude veto: macro headwinds too strong despite technical signals","claude_reasoning":"CPI remains at 4.2% and yield curve inverted. Technical alone insufficient."}
```

**EXIT_FORCED:**
```json
{"ts":"2026-04-28T11:30:00+00:00","symbol":"SPY","decision":"EXIT_FORCED","close_reason":"vix_spike_extreme: VIX=32.4","webhook_response":{"status":"executed"}}
```

**HOLDING:**
```json
{"ts":"2026-04-28T10:00:00+00:00","symbol":"SPY","decision":"HOLDING","position":{"opened_at":"2026-04-27T14:00:00+00:00","vix_regime_at_entry":"moderate"}}
```

---

## logs/trade_log.xlsx

Registro Excel acumulativo. **Una fila por ciclo SPY**, sin importar el resultado.

**Estructura de columnas:**

| Columna | Tipo | Ejemplo |
|---|---|---|
| `timestamp_utc` | datetime | 2026-04-27T14:00:00+00:00 |
| `cycle_id` | str | 2026-04-27_14-00-00 |
| `mode` | str | DRY_RUN / LIVE |
| `priority_cycle` | bool | True |
| `symbol` | str | SPY |
| `status` | str | ANALYZED / HOLDING / EXIT_FORCED / ... |
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
| `score_trend` | float | (legacy) |
| `score_sentiment` | float | (legacy) |
| `score_macro` | float | (legacy) |
| `score_vix` | float | (legacy) |
| `score_total` | float | 0.748 |
| `dim_macro` | float | 0.512 |
| `dim_technical` | float | 0.810 |
| `dim_components` | float | 0.740 |
| `dim_sentiment` | float | 0.630 |
| `dim_events` | float | 0.700 |
| `dim_cross_asset` | float | 0.680 |
| `dimensions_passing` | int | 5 |
| `claude_reasoning` | str | "Technical and cross-asset show bullish alignment..." |
| `confidence` | float | 0.748 |
| `size` | float | 0.12 |
| `trail_percent` | float | 4.0 |
| `take_profit_pct` | float o vacío | (vacío si null) |
| `max_holding_days` | int | 10 |
| `reason` | str | Score 0.748 / 5/6 dimensiones > 0.55 |
| `webhook_status` | str | sent / dry_run / failed / rejected / n/a |

**Nota:** Si el archivo está abierto en Excel al momento en que el agente intenta escribir, aparecerá una advertencia en el log y los datos se omitirán para ese ciclo (sin crashear el agente).

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
  "symbols": {
    "SPY": {
      "status": "ANALYZED",
      "decision": "APPROVE",
      "confidence": 0.748,
      "size": 0.12,
      "trail_percent": 4.0,
      "vix_regime": "moderate",
      "vix_value": 16.5,
      "dimension_scores": {
        "macro":       0.512,
        "technical":   0.810,
        "components":  0.740,
        "sentiment":   0.630,
        "events":      0.700,
        "cross_asset": 0.680
      },
      "dimensions_passing": 5,
      "claude_reasoning": "Technical and cross-asset dimensions show bullish alignment...",
      "reason": "Score 0.748 | 5/6 dimensiones > 0.55 | size=12% | trail=4.0%",
      "webhook_response": {
        "status": "executed",
        "order_id": "d43f5925-66bc-4227-81a6-7bb94faf3ab6"
      }
    }
  },
  "summary": {
    "approved":         ["SPY"],
    "exits":            [],
    "no_signal":        [],
    "holding":          [],
    "no_data":          [],
    "webhook_failed":   [],
    "rejected_by_bot1": []
  }
}
```
