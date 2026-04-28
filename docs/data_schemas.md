# Esquemas de Datos — agente01

Todos los archivos de estado viven en `state/`. Los reportes de ciclo en `logs/`. Ninguno se commitea (excluidos por `.gitignore`).

---

## Payload Webhook — Señal Activa (APPROVE)

Enviado a `POST http://127.0.0.1:8000/webhook/bot2` cuando `decision=APPROVE`.

```json
{
  "timestamp": "2026-04-27T14:00:00.123456+00:00",
  "status": "pending",
  "processed": false,
  "signal": {
    "strategy_id": "bot2_macro_research",
    "symbol": "SPY",
    "action": "buy",
    "confidence": 0.882,
    "size": 0.15,
    "params": {
      "source": "bot2",
      "stop_loss": 0.02,
      "take_profit": 0.04,
      "research_summary": "Score 0.882 | 3/3 señales alcistas | trend=bullish sentiment=positive macro=bullish",
      "score_breakdown": {
        "sentiment": 0.252,
        "trend":     0.300,
        "macro":     0.180,
        "news":      0.150
      }
    }
  }
}
```

**Campos del signal:**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `strategy_id` | str | Siempre `"bot2_macro_research"` |
| `symbol` | str | Símbolo en mayúsculas (ej: `"SPY"`) |
| `action` | str | `"buy"` (agente01 no hace short) |
| `confidence` | float | Score total del opportunity_scorer (0.0–1.0) |
| `size` | float | Fracción de capital: 0.05, 0.10 o 0.15 |
| `params.source` | str | Siempre `"bot2"` |
| `params.stop_loss` | float | `DEFAULT_STOP_LOSS` del .env (default: 0.02) |
| `params.take_profit` | float | `DEFAULT_TAKE_PROFIT` del .env (default: 0.04) |
| `params.research_summary` | str | Razón legible de la decisión |
| `params.score_breakdown.sentiment` | float | Contribución del sentimiento (raw_score × 0.30) |
| `params.score_breakdown.trend` | float | Contribución de la tendencia (raw_score × 0.30) |
| `params.score_breakdown.macro` | float | Contribución del Fear & Greed (raw_score × 0.25) |
| `params.score_breakdown.news` | float | Contribución del VIX (raw_score × 0.15) |

**Respuestas posibles de bot1:**

| Respuesta HTTP | Body | Significado |
|---|---|---|
| 200 | `{"status":"executed","order_id":"..."}` | Orden ejecutada en Alpaca |
| 200 | `{"status":"rejected","reason":"..."}` | bot1 pausado por su manager |
| 401 | `{"detail":"unauthorized bot2 webhook"}` | WEBHOOK_SECRET incorrecto |

---

## Payload Webhook — Sin Señal (NO_SIGNAL)

Enviado a bot1 al final del ciclo cuando **ningún símbolo** supera el umbral. Bot1 lo registra en su log como información.

```json
{
  "timestamp": "2026-04-27T10:00:00.123456+00:00",
  "status": "no_signal",
  "processed": false,
  "reason": "Ningún símbolo supera umbral 0.65 [SPY:0.45 | QQQ:0.38]",
  "signal": null
}
```

**Respuesta esperada de bot1:**
```json
{"status": "received_no_signal", "processed": true, "reason": "..."}
```

---

## state/last_signals.json

Control de cooldown. Registra cuándo se envió la última señal por símbolo.

```json
{
  "SPY": "2026-04-27T14:00:00.123456+00:00",
  "QQQ": "2026-04-27T10:00:00.456789+00:00"
}
```

- Se actualiza **solo** cuando bot1 confirma `"status":"executed"` (no en dry_run ni en rechazo).
- Si `now - last_signal < COOLDOWN_HOURS` → el símbolo se salta en el ciclo actual.

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
      "strategy_id": "bot2_macro_research",
      "symbol": "SPY",
      "action": "buy",
      "confidence": 0.78,
      "size": 0.10,
      "params": {
        "source": "bot2",
        "stop_loss": 0.02,
        "take_profit": 0.04,
        "research_summary": "Score 0.780 | 3/3 señales alcistas | trend=bullish sentiment=positive macro=bullish",
        "score_breakdown": {
          "sentiment": 0.216,
          "trend":     0.300,
          "macro":     0.170,
          "news":      0.098
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
{"ts":"2026-04-27T14:00:05+00:00","symbol":"SPY","decision":"APPROVE","action":"buy","confidence":0.882,"size":0.15,"reason":"Score 0.882 | 3/3 señales alcistas | trend=bullish sentiment=positive macro=bullish","webhook_response":{"status":"executed","order_id":"a1b2c3d4-..."},"dry_run":false}
```

**NO_SIGNAL:**
```json
{"ts":"2026-04-27T10:00:00+00:00","symbol":"QQQ","decision":"NO_SIGNAL","reason":"Score 0.420 < umbral 0.65","score":0.42}
```

**WEBHOOK_FAILED:**
```json
{"ts":"2026-04-27T14:00:10+00:00","symbol":"SPY","decision":"WEBHOOK_FAILED","action":"buy","error":"Connection refused"}
```

**REJECTED_BY_BOT1:**
```json
{"ts":"2026-04-27T14:00:08+00:00","symbol":"SPY","decision":"REJECTED_BY_BOT1","action":"buy","reason":"bot is paused by manager"}
```

---

## logs/YYYY-MM-DD_HH-MM-SS.json

Reporte completo de cada ciclo de ejecución. Se crea en `logs/` al finalizar cada ciclo.

```json
{
  "cycle_id": "2026-04-27_14-00-00",
  "started_at": "2026-04-27T14:00:00.000000+00:00",
  "finished_at": "2026-04-27T14:00:35.123456+00:00",
  "duration_seconds": 35.12,
  "mode": "LIVE",
  "market_open": true,
  "macro": {
    "fear_greed_score": 72.0,
    "fear_greed_label": "Greed",
    "vix": 14.2,
    "vix_regime": "low",
    "macro_bias": "bullish",
    "fetched_at": "2026-04-27T14:00:01.000000+00:00"
  },
  "symbols": {
    "SPY": {
      "status": "ANALYZED",
      "quote": {
        "price": 512.3,
        "prev_close": 506.25,
        "change_pct": 1.19,
        "volume": 85000000,
        "avg_volume": 60000000,
        "volume_ratio": 1.42,
        "sma20": 498.5,
        "price_vs_sma20": 2.77,
        "trend": "bullish"
      },
      "headlines_count": 12,
      "headlines": [
        {"title": "Fed signals pause in rate hikes", "source": "Reuters", "published_at": "2026-04-27T13:45:00Z"},
        {"title": "SPY breaks key resistance level", "source": "MarketWatch", "published_at": "2026-04-27T13:30:00Z"}
      ],
      "sentiment": {
        "compound": 0.68,
        "label": "positive",
        "positive_ratio": 0.75,
        "negative_ratio": 0.08
      },
      "score": {
        "sentiment": 0.84,
        "trend": 1.0,
        "macro": 0.72,
        "vix": 1.0,
        "total": 0.882
      },
      "decision": {
        "verdict": "APPROVE",
        "action": "buy",
        "confidence": 0.882,
        "size": 0.15,
        "reason": "Score 0.882 | 3/3 señales alcistas | trend=bullish sentiment=positive macro=bullish"
      },
      "webhook_response": {
        "status": "executed",
        "order_id": "d43f5925-66bc-4227-81a6-7bb94faf3ab6"
      }
    },
    "QQQ": {
      "status": "COOLDOWN"
    }
  },
  "summary": {
    "approved":         ["SPY"],
    "no_signal":        [],
    "cooldown":         ["QQQ"],
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
| `COOLDOWN` | Saltado por cooldown activo |
| `NO_DATA` | Sin datos de mercado (yfinance falló) |
