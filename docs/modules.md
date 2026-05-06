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
| `score_total` | Score total ponderado (0.0–1.0) |
| `dim_macro` | Score dimensión Macro (0.0–1.0) |
| `dim_technical` | Score dimensión Técnico (0.0–1.0) |
| `dim_components` | Score dimensión Componentes (0.0–1.0) |
| `dim_sentiment` | Score dimensión Sentimiento (0.0–1.0) |
| `dim_events` | Score dimensión Eventos (0.0–1.0) |
| `dim_cross_asset` | Score dimensión Cross-Assets (0.0–1.0) |
| `dimensions_passing` | Número de dims con score > 0.55 (0–6) |
| `claude_reasoning` | Razonamiento narrativo de Claude AI |
| `confidence` | Score final ajustado |
| `size` | Fracción de capital: 0.08 / 0.12 / 0.18 / 0.25 (4 tiers) |
| `trail_percent` | Trailing stop % (3.0/4.0/5.5) — solo en APPROVE |
| `take_profit_pct` | TP % (null o 8.0) — solo en APPROVE |
| `max_holding_days` | Días máximos de la posición |
| `reason` | Razón legible de la decisión |
| `webhook_status` | sent / dry_run / failed / rejected / n/a |

---

## run_analysis.py — Análisis Manual SPY Specialist

Script para ejecutar el ciclo SPY Specialist completo **ignorando el horario de mercado**. Útil para verificación y testing fuera del horario de trading.

Siempre corre en modo `DRY_RUN=True` — nunca envía webhook real a bot1.

```bash
python run_analysis.py
```

Imprime: las 6 dimensiones con scores y contribuciones ponderadas, resultado del pipeline de filtros (gate), VIX y trail config, razonamiento de Claude AI, y el payload que se enviaría si fuera APPROVE.

---

## test_integration.py — Prueba de Integración Real

Script para probar la integración completa end-to-end: investigación SPY Specialist real + webhook real a bot1 + escritura en Excel y decision_log. Ignora el horario de mercado.

**A diferencia de `run_analysis.py`, este script SÍ envía el webhook a bot1** (DRY_RUN=False forzado internamente).

```bash
python test_integration.py
```

Ejecuta los 4 pasos:
1. `spy_cycle.run("SPY")` — 6 dimensiones + Claude AI real
2. `webhook_client.send(payload)` — envío real a bot1
3. `append_excel_rows([row])` — escribe fila en `logs/trade_log.xlsx`
4. Append a `state/decision_log.jsonl`

Útil para verificar la integración completa antes de dejar el agente en producción.

---

## research/yf_client.py

Wrapper seguro para Yahoo Finance con circuit breaker automático.

- Al primer error 429 / rate-limit → bloquea todas las llamadas durante ~55 minutos.
- `reset()` al inicio de cada ciclo para darle a Yahoo una nueva oportunidad.
- `safe_history(symbol, **kwargs)` → `pd.DataFrame | None`
- `safe_download(symbols, **kwargs)` → `pd.DataFrame | None`
- `is_blocked()` → bool

---

## research/td_client.py

Cliente REST para Twelve Data (free tier: 800 calls/día) con circuit breaker y contador diario.

- Soporta los mismos símbolos que yfinance con mapeo automático (ej. `BTC-USD` → `BTC/USD`, `DX-Y.NYB` → `DXY`).
- `safe_time_series(yf_symbol, interval, outputsize)` → `pd.DataFrame | None`
- `safe_batch_close(yf_symbols, interval, outputsize)` → `dict[str, pd.DataFrame | None]`
- `remaining_calls()` → int (cuota diaria restante)
- `is_blocked()` → bool (verifica circuito Y cuota)
- `reset()` → limpia el bloqueo temporal; el contador diario persiste entre ciclos.

---

## research/market_data.py

Obtiene datos de precio y tendencia usando **Yahoo Finance y Twelve Data simultáneamente** (sin API key para Yahoo; `TWELVE_DATA_API_KEY` para TD).

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

**Lógica de fuentes dual:**
- Yahoo y Twelve Data se llaman siempre en simultáneo.
- Si ambos disponibles: usa Yahoo; rellena `Volume` con TD si Yahoo lo trae vacío.
- Si solo uno disponible: usa el que respondió.
- Si ambos fallan: retorna `None` → SPY Specialist continúa con score neutral en la dimensión afectada.

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `get_quote(symbol)` | Retorna `Quote` o `None` si ambas fuentes fallan |
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

## analysis/spy_cycle.py — Orquestador SPY Specialist

Ejecuta el ciclo completo de investigación SPY: llama a los 6 módulos de dimensión, aplica el pipeline de filtros en cascada y llama a Claude para la decisión final.

**Función principal:** `run(symbol="SPY") → SpyCycleResult`

Nunca lanza excepción. Si una dimensión falla, usa valores neutros (0.5) y continúa.

**`SpyCycleResult`:**
```
decision         str    "APPROVE" | "NO_SIGNAL"
action           str    "buy" | "none"
confidence       float  score total ponderado (0.0–1.0)
size             float  fracción de capital (0.08/0.12/0.18/0.25)
trail_percent    float  trailing stop % ajustado al régimen VIX
reason           str    razón del filtro cascada
claude_reasoning str    análisis narrativo de Claude
symbol           str    símbolo analizado
vix_regime       str    "low" | "moderate" | "high" | "extreme"
vix_value        float  valor VIX spot
filter_result    FilterResult  resultado completo del pipeline de filtros
dimension_scores DimensionScores  scores de las 6 dimensiones
```

---

## analysis/claude_analyst.py — Motor de Decisión Claude

Llama a Claude API (via Anthropic SDK) con los datos estructurados del ciclo SPY.
El system prompt estable se cachea (`cache_control: ephemeral`) para reducir costos.

**Función principal:** `analyze(filter_result, market_snapshot) → ClaudeAnalysis`

- Modelo: `CLAUDE_MODEL` del .env (default: `claude-haiku-4-5-20251001`)
- Salida: JSON estructurado `{decision, action, confidence, size, trail_percent, reasoning}`
- Fallback: `NO_SIGNAL` con `confidence=0.0` en caso de cualquier error de API

**`ClaudeAnalysis`:**
```
decision       str    "APPROVE" | "NO_SIGNAL"
action         str    "buy" | "none"
confidence     float  confianza del modelo (0.0–1.0)
size           float  tamaño sugerido
trail_percent  float  trailing stop sugerido
reasoning      str    explicación en 2–3 oraciones
```

**Costo estimado (Haiku 4.5):** ~$0.0002/ciclo con prompt caching activo.

---

## analysis/filters.py — Pipeline de Filtros en Cascada

Aplica 4 pasos secuenciales antes de aprobar una señal SPY.

| Paso | Mecanismo | Resultado |
|---|---|---|
| 1 | Vetos duros | NO_SIGNAL inmediato si VIX>30, FOMC<24h, earnings≥3, RSI>75, precio<SMA200, curva muy invertida |
| 2 | Score compuesto | Suma ponderada de las 6 dimensiones (0.0–1.0) |
| 3 | Filtros suaves | Multiplica score por evento moderado (×0.85) y ajusta trail |
| 4 | Validación final | `score ≥ MIN_CONFIDENCE(0.72)` AND `≥5/6 dimensiones > 0.55` |

**Función principal:** `evaluate(scores, vix_regime, ...) → FilterResult`

---

## analysis/dimension_scorers/ — Scorers por Dimensión

Seis módulos, uno por dimensión. Todos producen un `total` normalizado 0.0–1.0.

| Módulo | Entradas clave | Lógica |
|--------|---------------|--------|
| `macro_scorer.py` | inflation, employment, rates, fed_score, yield_curve_spread | Veto si spread<-0.50 Y total<0.35 |
| `technical_scorer.py` | overall_score, bullish_count, rsi_veto, sma200_veto, atr_veto | Vetos fuerzan total=0; bonus alineación TFs |
| `components_scorer.py` | top10_score, sector_score, earnings_veto | earnings_veto fuerza total=0 |
| `sentiment_scorer.py` | fear_greed (0-1), vix_term, put_call, vader | Pesos: F&G 30%, VIX term 25%, P/C 20%, VADER 25% |
| `events_scorer.py` | score_multiplier, veto, geopolitics_score | Veto FOMC/extreme → total=0 |
| `cross_asset_scorer.py` | cross_asset_score, divergences | -0.10 por cada divergencia detectada |

---

## research/macro/ — Dimensión Macro (25%)

| Módulo | Fuente | Datos |
|--------|--------|-------|
| `fred_client.py` | FRED API (FRED_API_KEY) | Client genérico con cache 4h en `state/fred_cache/` |
| `inflation.py` | CPIAUCSL, PCEPILFE | CPI YoY, Core PCE, score 0-1 |
| `employment.py` | UNRATE, IC4WSA, PAYEMS | Desempleo, jobless claims, nóminas |
| `rates.py` | DFF, DGS10, DGS2, T10Y2Y | Fed Funds Rate, yield curve spread (10Y-2Y) |
| `fed_watch.py` | CME FedWatch / inferencia | Probabilidades hike/cut/hold, fed_stance |

---

## research/technical/ — Dimensión Técnico (20%)

| Módulo | Descripción |
|--------|-------------|
| `indicators.py` | SMA9/20/50/200, EMA9, RSI14, MACD, Bollinger Bands, ATR14, vol_ratio |
| `key_levels.py` | Máximos/mínimos de 20d/50d/52w, distancia al máximo de 52 semanas |
| `multi_timeframe.py` | Descarga 1D/4H/1H de yfinance, score por TF, alineación, vetos RSI/SMA200/ATR |

**Vetos técnicos duros:**
- `rsi_veto`: RSI diario > 75 (sobrecompra extrema)
- `sma200_veto`: precio < SMA200 diaria (régimen bajista)
- `atr_veto`: ATR > 2x media 30d (volatilidad anómala, penaliza -0.15)

---

## research/components/ — Dimensión Componentes (20%)

| Módulo | Descripción |
|--------|-------------|
| `top_holdings.py` | SPY top-10 con pesos estáticos. Score = promedio ponderado del % 1d de cada holding |
| `sectors.py` | 11 ETFs sectoriales SPDR. Score por breadth (# sectores en verde) |
| `earnings_calendar.py` | yfinance.ticker.calendar para top-10. Veto si ≥3 reportan en 48h |

---

## research/events/ — Dimensión Eventos (10%)

| Módulo | Descripción |
|--------|-------------|
| `fomc_calendar.py` | Parsea fed.gov para fechas FOMC. Cache 24h en `state/upcoming_events.json` |
| `economic_calendar.py` | Scraping Trading Economics. Evento EXTREME <12h → veto. HIGH <24h → ×0.85 |
| `geopolitics_news.py` | Reuters RSS + NewsAPI. Clasifica riesgo geopolítico en bajo/medio/alto |

---

## research/sentiment/ — Dimensión Sentimiento (15%)

| Módulo | Descripción |
|--------|-------------|
| `vix_term_structure.py` | Descarga ^VIX9D, ^VIX, ^VIX3M. Contango=0.85, flat=0.55, backwardation=0.20 |
| `put_call_ratio.py` | Scraping CBOE. Ratio>1.20 → contrarian bullish (score 0.75). Ratio<0.70 → bearish |

---

## research/cross_assets/ — Dimensión Cross-Assets (10%)

| Módulo | Descripción |
|--------|-------------|
| `correlations.py` | Descarga DXY, TLT, GLD, USO, BTC-USD, HYG, QQQ. Detecta divergencias SPY vs activos |

**Divergencias detectadas:** SPY+DXY (presión multinacionales), SPY+HYG- (institucionales reducen riesgo), SPY-+TLT+ (flight to safety).

---

## sender/signal_formatter.py

Construye los payloads JSON exactos que espera el endpoint `/webhook/bot2` de bot1.

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `get_trail_config(vix_regime)` | Retorna `{trail_percent, take_profit_pct, max_holding_days}` segun VIX |
| `build_spy_payload(result, vix_regime)` | Payload SPY Specialist con 6-dim breakdown + claude_reasoning |
| `build_payload(result, vix_regime)` | Payload legacy (APPROVE BUY) con 4-componente breakdown |
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
