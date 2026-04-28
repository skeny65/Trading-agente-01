# Referencia de Módulos — agente01

---

## agente01.py — Orquestador Principal

Entry point del agente. Configura logging, ejecuta el ciclo de investigación y programa ejecuciones periódicas con APScheduler (BlockingScheduler, timezone America/New_York).

**Funciones internas:**

| Función | Descripción |
|---------|-------------|
| `run_cycle()` | Ciclo completo: retry_pending → exit evaluator → macro → quotes → por símbolo: análisis/decisión/envío → Excel → reporte |
| `_is_market_hours()` | True si es día hábil entre 9:30–16:00 ET |
| `_is_priority_cycle()` | True si la hora ET está dentro de 5 min de 09:45, 12:30 o 15:30 |
| `_excel_row(...)` | Construye un dict con todas las columnas del Excel para un símbolo/ciclo |
| `_is_on_cooldown(symbol, last_signals)` | True si ya se envió señal dentro de COOLDOWN_HOURS (24h) |
| `_mark_signal_sent(symbol, last_signals)` | Actualiza `last_signals.json` con timestamp actual |
| `_load_last_signals()` / `_save_last_signals()` | Lee/escribe `state/last_signals.json` |
| `_load_open_positions()` / `_save_open_positions()` | Lee/escribe `state/open_positions.json` |
| `_add_open_position(symbol, vix_regime, trail_config, result)` | Agrega posición al seguimiento tras confirmación de bot1 |
| `_remove_open_position(symbol)` | Elimina posición tras cierre forzado exitoso |
| `_log_decision(entry)` | Append a `state/decision_log.jsonl` |
| `_write_cycle_report(report)` | Escribe reporte JSON en `logs/YYYY-MM-DD_HH-MM-SS.json` |

**Ciclo de ejecución:**
1. Al arrancar: valida config → ejecuta ciclo inmediato → arranca scheduler
2. Cada `CYCLE_INTERVAL_MINUTES` minutos (default: 60): `run_cycle()` automático
3. Si mercado cerrado: escribe reporte `market_open=false` y termina el ciclo
4. Si mercado abierto: Fase 1 (exits) → Fase 2 (macro+precios) → Fase 3 (análisis) → Fase 4 (persistencia)

**Ciclos prioritarios** (marcados `[PRIORITY]` en logs):
- 09:45 ET — post-apertura, mercado asentado
- 12:30 ET — media sesión, momentum USA puro
- 15:30 ET — pre-cierre, última decisión del día

---

## excel_logger.py — Registro Excel

Módulo en la raíz del proyecto. Escribe una fila por símbolo por ciclo en `logs/trade_log.xlsx`, acumulando el historial completo de todas las decisiones.

**Función:** `append_excel_rows(rows: list[dict]) -> None`

- Si el archivo no existe: lo crea con la fila de cabeceras.
- Si el archivo está abierto en Excel: advierte en el log sin crashear el agente.
- Si `openpyxl` no está instalado: advierte y no hace nada.

**Columnas del Excel (en orden):**

| Columna | Contenido |
|---------|-----------|
| `timestamp_utc` | Hora de inicio del ciclo (ISO) |
| `cycle_id` | ID del ciclo (YYYY-MM-DD_HH-MM-SS) |
| `mode` | DRY_RUN / LIVE |
| `priority_cycle` | True si es ciclo prioritario (09:45/12:30/15:30 ET) |
| `symbol` | Símbolo analizado (SPY, QQQ, etc.) |
| `status` | ANALYZED / HOLDING / HOLDING_OK / COOLDOWN / NO_DATA / EXIT_FORCED / EXIT_NO_DATA |
| `decision` | APPROVE / NO_SIGNAL / HOLDING / COOLDOWN / NO_DATA / EXIT_FORCED / EXIT_CHECK_OK |
| `action` | buy / close / none |
| `price` | Precio de cierre |
| `change_pct` | % de cambio diario |
| `sma20` | Media móvil 20 días |
| `sma50` | Media móvil 50 días |
| `trend_strength` | strong_bullish / bullish / neutral / bearish / strong_bearish |
| `volume_ratio` | Volume / avg_volume |
| `sentiment_compound` | Score VADER -1.0 a +1.0 |
| `sentiment_label` | positive / neutral / negative |
| `fear_greed_score` | CNN Fear & Greed 0–100 |
| `fear_greed_label` | Extreme Fear / Fear / Neutral / Greed / Extreme Greed |
| `vix` | Valor actual del VIX |
| `vix_regime` | low / moderate / high / extreme |
| `score_trend` | Score bruto de tendencia (0.0–1.0) |
| `score_sentiment` | Score bruto de sentimiento (0.0–1.0) |
| `score_macro` | Score bruto de macro (0.0–1.0) |
| `score_vix` | Score bruto de VIX (0.0–1.0) |
| `score_total` | Score total ponderado (0.0–1.0) |
| `confidence` | Mismo que score_total |
| `size` | Fracción de capital asignada (0.03/0.05/0.08) |
| `trail_percent` | Trailing stop % (3.0/4.0/5.5) — solo en APPROVE |
| `take_profit_pct` | TP % (null o 8.0) — solo en APPROVE |
| `max_holding_days` | Días máximos de la posición |
| `reason` | Razón legible de la decisión |
| `webhook_status` | sent / dry_run / failed / rejected / n/a |

---

## run_analysis.py — Análisis Manual

Script para ejecutar un ciclo completo de análisis **ignorando el horario de mercado**. Útil para testing y verificación fuera del horario de trading.

Siempre corre en modo `DRY_RUN=True` aunque el .env diga lo contrario.

```bash
python run_analysis.py
```

Imprime: macro context (VIX, Fear&Greed, trail config), datos por símbolo (precio, SMA20, SMA50, trend_strength, sentimiento, score breakdown, decisión), y el payload exacto que se enviaría a bot1.

---

## research/market_data.py

Obtiene datos de precio y tendencia de Yahoo Finance (sin API key).

**Dataclass `Quote`:**
```
symbol          str     Símbolo (ej: "SPY")
price           float   Precio actual de cierre
prev_close      float   Cierre del día anterior
change_pct      float   % de cambio vs cierre anterior
volume          int     Volumen del día actual
avg_volume      int     Volumen promedio (ultimos 60 días)
volume_ratio    float   volume / avg_volume  (>1 = más activo de lo normal)
sma20           float   Media móvil simple de 20 cierres
sma50           float   Media móvil simple de 50 cierres
price_vs_sma20  float   % por encima/debajo de SMA20
trend           str     "bullish" | "bearish" | "neutral"
trend_strength  str     "strong_bullish" | "bullish" | "neutral" | "bearish" | "strong_bearish"
fetched_at      str     ISO timestamp UTC
```

**Lógica de trend_strength:**
```
precio > SMA20 > SMA50  →  "strong_bullish"  (score base 1.00)
precio > SMA20           →  "bullish"          (score base 0.75)
precio aprox. SMA20      →  "neutral"          (score base 0.50)
precio < SMA20           →  "bearish"          (score base 0.25)
precio < SMA20 < SMA50   →  "strong_bearish"   (score base 0.00)
```

**Historial:** 60 días (necesario para calcular SMA50 con suficientes datos).

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `get_quote(symbol)` | Retorna `Quote` o `None` si falla |
| `get_quotes(symbols)` | Procesa lista completa, retorna `dict[str, Quote]` |

---

## research/macro_indicators.py

Obtiene el contexto macroeconómico global del mercado. Se ejecuta **una sola vez por ciclo** y el resultado es compartido por todos los símbolos del WATCHLIST.

**Fuentes:**
- **Fear & Greed**: `production.dataviz.cnn.io/index/fearandgreed/graphdata` — sin key, fallback a 50 si bloquea (error 418)
- **VIX**: Yahoo Finance ticker `^VIX` — sin key, fallback a 20.0

**Dataclass `MacroContext`:**
```
fear_greed_score   float   0–100 (0=Extreme Fear, 100=Extreme Greed)
fear_greed_label   str     "Extreme Fear"|"Fear"|"Neutral"|"Greed"|"Extreme Greed"
vix                float   Valor actual del VIX
vix_regime         str     "low"(<15) | "moderate"(15–20) | "high"(20–30) | "extreme"(>=30)
macro_bias         str     "bullish" | "bearish" | "neutral"
fetched_at         str     ISO timestamp UTC
```

**Lógica de macro_bias:**
```
+1 bullish si fear_greed >= 60
+1 bullish si vix < 20
+1 bearish si fear_greed <= 40
+1 bearish si vix > 25
→ macro_bias = "bullish" si bullish > bearish
→ macro_bias = "bearish" si bearish > bullish
→ macro_bias = "neutral" si empate
```

**Función principal:** `get_macro_context() → MacroContext`

---

## research/news_fetcher.py

Obtiene titulares recientes de prensa financiera via NewsAPI.

**Dataclass `Headline`:**
```
title        str   Título del artículo
description  str   Descripción/resumen
source       str   Nombre del medio (ej: "Reuters")
published_at str   ISO timestamp de publicación
```

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `fetch(symbol, hours=None)` | Titulares de las últimas N horas. Si hours=None usa config.NEWS_LOOKBACK_HOURS (4h). Lista vacía si falla. |

**Notas:**
- Plan gratuito de NewsAPI: 100 requests/día
- Con WATCHLIST=8 símbolos y ciclos de 1h = hasta 8 requests/ciclo durante las 6.5h de mercado
- Si `NEWSAPI_KEY` está vacío → retorna lista vacía sin error
- Filtra por `publishedAt` para quedarse solo con noticias dentro de la ventana temporal

---

## analysis/sentiment_analyzer.py

Convierte los titulares de texto en una señal numérica usando VADER NLP (corre completamente local, sin API externa).

**Dataclass `SentimentResult`:**
```
compound         float   Promedio de scores compound (-1.0 a +1.0)
positive_ratio   float   % de titulares con compound >= +0.05
negative_ratio   float   % de titulares con compound <= -0.05
headline_count   int     Total de titulares analizados
label            str     "positive" | "neutral" | "negative"
```

**Lógica de label:**
```
compound >= +0.05  →  "positive"
compound <= -0.05  →  "negative"
entre -0.05/+0.05 →  "neutral"
```

**Función principal:** `analyze(headlines) → SentimentResult`

Con 0 titulares retorna compound=0.0, label="neutral". No lanza error.

---

## analysis/opportunity_scorer.py

Calcula el score de oportunidad compuesto (0.0–1.0) combinando los 4 componentes.

**Dataclass `ScoreBreakdown`:**
```
sentiment   float   Score bruto del sentimiento (0.0–1.0)
trend       float   Score bruto de la tendencia (0.0–1.0)
macro       float   Score bruto del Fear & Greed (0.0–1.0)
vix         float   Score bruto del VIX (0.0–1.0)
total       float   Score final ponderado (0.0–1.0)
```

**Pesos y cálculo:**

| Componente | Peso | Fuente | Cálculo |
|-----------|------|--------|---------|
| Tendencia | **40%** | yfinance | strength_map[trend_strength] + vol_bonus |
| Sentimiento | **20%** | VADER | `(compound + 1) / 2` |
| Macro (F&G) | **25%** | CNN | `fear_greed_score / 100` |
| VIX | **15%** | yfinance | low=1.0, moderate=0.65, high=0.30, extreme=0.0 |

```
total = trend×0.40 + sentiment×0.20 + macro×0.25 + vix×0.15
```

**Lógica de trend_score:**
```python
strength_map = {
    "strong_bullish": 1.00,
    "bullish":        0.75,
    "neutral":        0.50,
    "bearish":        0.25,
    "strong_bearish": 0.00,
}
base = strength_map[quote.trend_strength]
vol_bonus = min((volume_ratio - 1.0) × 0.1, 0.10) si volume_ratio > 1.0 else 0
trend_score = min(base + vol_bonus, 1.0)
```

**Función principal:** `calculate(quote, sentiment, macro) → ScoreBreakdown`

---

## analysis/decision_engine.py

Aplica las reglas de negocio para decidir si generar una señal de compra.

**Enum `Decision`:** `APPROVE` | `REJECT` | `NO_SIGNAL`

**Dataclass `EvaluationResult`:**
```
decision     Decision       Veredicto final
action       str            "buy" | "close" | "none"
confidence   float          Score total
size         float          Fracción de capital (0.03 / 0.05 / 0.08)
reason       str            Explicación legible del veredicto
symbol       str            Símbolo evaluado
score        ScoreBreakdown Desglose completo de los 4 componentes
```

**Reglas (en orden):**

| Regla | Condición | Resultado |
|---|---|---|
| Regla 0 | `vix_regime == "extreme"` | NO_SIGNAL — no se abren posiciones |
| Regla 1 | `score.total < 0.70` | NO_SIGNAL |
| Regla 2 | Consenso 3/3 bullish | APPROVE BUY |
| Regla 2b | 2+ bearish | NO_SIGNAL (sin operaciones cortas) |
| Regla 2c | Mixto / insuficiente | NO_SIGNAL |

**Consenso 3/3 (todos deben ser bullish):**
```
quote.trend == "bullish"        (derivado de price_vs_sma20)
sentiment.label == "positive"   (VADER compound >= +0.05)
macro.macro_bias == "bullish"   (F&G y VIX combinados)
```

**Tamaño dinámico:**
```
score >= 0.85  →  size = 0.08  (SIZE_HIGH_CONFIDENCE)
score >= 0.78  →  size = 0.05  (SIZE_MEDIUM_CONFIDENCE)
score >= 0.70  →  size = 0.03  (SIZE_LOW_CONFIDENCE)
```

**Función principal:** `evaluate(symbol, quote, sentiment, macro, score) → EvaluationResult`

---

## analysis/exit_evaluator.py

Evalúa si una posición abierta debe cerrarse **antes de que el trailing stop de Alpaca se active**. Se ejecuta en Fase 1 del ciclo para cada posición en `open_positions.json`.

**Dataclass `ExitSignal`:**
```
should_close  bool   True si algún trigger está activo
reason        str    Descripción del trigger ("vix_spike_extreme: VIX=32.4")
```

**Los 4 triggers de cierre forzado:**

| # | Trigger | Condición | Razón en el payload |
|---|---|---|---|
| 1 | VIX extremo | `vix_regime == "extreme"` | `vix_spike_extreme` |
| 2 | Reversión con volumen | `trend == "bearish"` AND `volume_ratio > 1.5` | `trend_reversal_with_volume` |
| 3 | Crash de sentimiento | `compound < -0.5` AND `headline_count >= 5` | `sentiment_crash` |
| 4 | Tiempo máximo | `elapsed_days >= max_holding_days` de la posición | `max_holding_reached` |

**Función principal:** `evaluate_exit(symbol, quote, sentiment, macro, position) → ExitSignal`

Si `should_close == True` → agente01 envía `build_close_payload` a bot1 con `action="close"`.

---

## sender/signal_formatter.py

Construye los payloads JSON exactos que espera el endpoint `/webhook/bot2` de bot1.

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `get_trail_config(vix_regime)` | Retorna `{trail_percent, take_profit_pct, max_holding_days}` segun VIX |
| `build_payload(result, vix_regime)` | Payload de apertura (APPROVE BUY) con trailing dinámico |
| `build_close_payload(symbol, close_reason)` | Payload de cierre forzado (action="close") |
| `build_no_signal_payload(reason)` | Payload informativo (status="no_signal") |

**Trail config por régimen VIX:**
```
"low"      →  trail_percent=3.0,  take_profit_pct=null, max_holding_days=15
"moderate" →  trail_percent=4.0,  take_profit_pct=null, max_holding_days=10
"high"     →  trail_percent=5.5,  take_profit_pct=8.0,  max_holding_days=7
"extreme"  →  no se llama (bloqueado en Regla 0)
```

**strategy_id**: `"bot2_swing_trailing"` — identifica esta estrategia en el BotRegistry de bot1.

---

## sender/webhook_client.py

Gestiona el envío HTTP a bot1 con resiliencia ante fallos de red.

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `send(payload)` | Envía a bot1. Maneja DRY_RUN, rejected, received_no_signal, y fallo de red |
| `retry_pending()` | Reintenta todos los payloads en `pending_signals.json` |
| `_post(payload, headers)` | Lógica de reintento con backoff exponencial |
| `_save_to_pending(payload)` | Agrega a `state/pending_signals.json` |

**Comportamiento por respuesta de bot1:**

| Respuesta | Acción de agente01 |
|-----------|-------------------|
| `status="executed"` | Exito — cooldown + open_position activados |
| `status="rejected"` | Log + Telegram — no reintenta |
| `status="received_no_signal"` | Confirmación OK |
| `status="failed"` (agotó reintentos) | Guarda en `pending_signals.json` + Telegram |
| HTTP 4xx | Log error — no reintenta |

**Backoff:** 5s → 10s → 15s entre intentos (3 máximo).

---

## sender/telegram_notifier.py

Alertas opcionales a Telegram. Si `TELEGRAM_BOT_TOKEN` o `TELEGRAM_CHAT_ID` están vacíos → no-op (sin error).

| Función | Cuándo | Mensaje |
|---------|--------|---------|
| `signal_sent(symbol, action, confidence, size, trail_pct, vix_regime)` | APPROVE ejecutado | ✅ Señal enviada + trail% + VIX régimen |
| `signal_rejected(symbol, action, reason)` | bot1 rechaza | ⚠️ Rechazada + razón |
| `webhook_failed(symbol, error)` | 3 intentos agotados | ❌ En cola pendiente |
| `position_closed(symbol, reason)` | Cierre forzado exitoso | 🚪 Trigger de cierre + razón |
| `no_signal_cycle(summary)` | Ciclo sin aprobados | 🔍 Scores de todos los símbolos |
