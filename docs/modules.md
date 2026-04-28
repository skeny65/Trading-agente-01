# Referencia de Módulos — agente01

---

## agente01.py — Orquestador Principal

Entry point del agente. Configura logging, ejecuta el ciclo de investigación y programa ejecuciones periódicas con APScheduler.

**Funciones internas:**

| Función | Descripción |
|---------|-------------|
| `run_cycle()` | Ciclo completo: retry_pending → macro → quotes → por símbolo: news/sentiment/score/decision/send → no_signal si ninguno aprobado → reporte |
| `_is_market_hours()` | True si es día hábil entre 9:30–16:00 ET |
| `_is_on_cooldown(symbol, last_signals)` | True si ya se envió señal del símbolo dentro de COOLDOWN_HOURS |
| `_mark_signal_sent(symbol, last_signals)` | Actualiza `last_signals.json` con timestamp actual |
| `_load_last_signals()` / `_save_last_signals()` | Lee/escribe `state/last_signals.json` |
| `_log_decision(entry)` | Append a `state/decision_log.jsonl` |
| `_write_cycle_report(report)` | Escribe el reporte JSON completo en `logs/YYYY-MM-DD_HH-MM-SS.json` |

**Ciclo de ejecución:**
1. Al arrancar: valida config → ejecuta ciclo inmediato → arranca scheduler
2. Cada `CYCLE_INTERVAL_HOURS` horas: `run_cycle()` automático
3. Si mercado cerrado: escribe reporte `market_open=false` y termina el ciclo

---

## run_analysis.py — Análisis Manual

Script para ejecutar un ciclo completo de análisis **ignorando el horario de mercado**. Útil para testing y verificación de la integración.

Siempre corre en modo `DRY_RUN=True` aunque el .env diga lo contrario.

```bash
python run_analysis.py
```

Imprime: macro context, datos por símbolo (precio, tendencia, sentimiento, score, decisión), y el payload exacto que se enviaría a bot1.

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
avg_volume      int     Volumen promedio (últimos 30 días)
volume_ratio    float   volume / avg_volume  (>1 = más activo de lo normal)
sma20           float   Media móvil simple de 20 cierres
price_vs_sma20  float   % por encima/debajo de SMA20
trend           str     "bullish" | "bearish" | "neutral"
fetched_at      str     ISO timestamp UTC
```

**Lógica de trend:**
```
price_vs_sma20 > +1%  →  "bullish"
price_vs_sma20 < -1%  →  "bearish"
entre -1% y +1%       →  "neutral"
```

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `get_quote(symbol)` | Retorna `Quote` o `None` si falla |
| `get_quotes(symbols)` | Procesa lista completa, retorna `dict[str, Quote]` |

---

## research/macro_indicators.py

Obtiene el contexto macroeconómico global del mercado. Se ejecuta una sola vez por ciclo y el resultado es compartido por todos los símbolos del WATCHLIST.

**Fuentes:**
- **Fear & Greed**: `production.dataviz.cnn.io/index/fearandgreed/graphdata` — sin key, fallback a 50 si bloquea
- **VIX**: Yahoo Finance ticker `^VIX` — sin key, fallback a 20.0

**Dataclass `MacroContext`:**
```
fear_greed_score   float   0–100 (0=Extreme Fear, 100=Extreme Greed)
fear_greed_label   str     "Extreme Fear"|"Fear"|"Neutral"|"Greed"|"Extreme Greed"
vix                float   Valor actual del VIX
vix_regime         str     "low"(<15) | "moderate"(15–20) | "high"(20–30) | "extreme"(≥30)
macro_bias         str     "bullish" | "bearish" | "neutral"
fetched_at         str     ISO timestamp UTC
```

**Lógica de macro_bias:**
```
+1 bullish si fear_greed ≥ 60
+1 bullish si vix < 20
+1 bearish si fear_greed ≤ 40
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
| `fetch(symbol, hours=6)` | Titulares de las últimas N horas para el símbolo. Lista vacía si falla. |

**Notas:**
- Plan gratuito de NewsAPI: 100 requests/día
- Con WATCHLIST=["SPY","QQQ"] y 4h de ciclo: ~12 requests/día
- Si `NEWSAPI_KEY` está vacío → retorna lista vacía sin error
- Filtra por `publishedAt` para quedarse solo con noticias dentro de la ventana temporal

---

## analysis/sentiment_analyzer.py

Convierte los titulares de texto en una señal numérica usando VADER NLP (corre completamente local, sin API externa).

**Dataclass `SentimentResult`:**
```
compound         float   Promedio de scores compound (-1.0 a +1.0)
positive_ratio   float   % de titulares con compound ≥ +0.05
negative_ratio   float   % de titulares con compound ≤ -0.05
headline_count   int     Total de titulares analizados
label            str     "positive" | "neutral" | "negative"
```

**Lógica de label:**
```
compound ≥ +0.05  →  "positive"
compound ≤ -0.05  →  "negative"
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
| Sentimiento | 30% | VADER | `(compound + 1) / 2` |
| Tendencia | 30% | yfinance | bullish=1.0, neutral=0.5, bearish=0.0 + vol_bonus |
| Macro (F&G) | 25% | CNN | `fear_greed_score / 100` |
| VIX | 15% | yfinance | low=1.0, moderate=0.65, high=0.30, extreme=0.0 |

`total = sentiment×0.30 + trend×0.30 + macro×0.25 + vix×0.15`

**Función principal:** `calculate(quote, sentiment, macro) → ScoreBreakdown`

---

## analysis/decision_engine.py

Aplica las reglas de negocio para decidir si generar una señal.

**Enum `Decision`:** `APPROVE` | `REJECT` | `NO_SIGNAL`

**Dataclass `EvaluationResult`:**
```
decision     Decision       Veredicto final
action       str            "buy" | "sell" | "none"
confidence   float          Score total
size         float          Fracción de capital (0.05 / 0.10 / 0.15)
reason       str            Explicación legible del veredicto
symbol       str            Símbolo evaluado
score        ScoreBreakdown Desglose completo de los 4 componentes
```

**Reglas (en orden):**

1. `score.total < MIN_CONFIDENCE` → `NO_SIGNAL` ("Score X < umbral Y")
2. Consenso de señales cualitativas:
   - ≥ 2 de {trend, sentiment.label, macro_bias} son "bullish" → `APPROVE BUY`
   - ≥ 2 son "bearish" → `NO_SIGNAL` (agente01 no opera en corto)
   - mixto → `NO_SIGNAL`

**Tamaño dinámico:**
```
score ≥ 0.85  →  size = 0.15
score ≥ 0.75  →  size = 0.10
score ≥ 0.65  →  size = 0.05
```

**Función principal:** `evaluate(symbol, quote, sentiment, macro, score) → EvaluationResult`

---

## sender/signal_formatter.py

Construye el payload JSON exacto que espera el endpoint `/webhook/bot2` de bot1.

**Función:** `build_payload(result) → dict`

- Para `APPROVE`: `status="pending"`, incluye `strategy_id="bot2_macro_research"`, `source="bot2"`, `research_summary`, `score_breakdown` con contribuciones ponderadas (`sentiment×0.30`, `trend×0.30`, `macro×0.25`, `vix×0.15` → mapeado como `news`).
- Para `NO_SIGNAL` (si se llama): `status="no_signal"` con `reason` y `signal=null`.

---

## sender/webhook_client.py

Gestiona el envío HTTP a bot1 con resiliencia ante fallos de red.

**Funciones:**

| Función | Descripción |
|---------|-------------|
| `send(payload)` | Envía a bot1. Maneja DRY_RUN, rejected, received_no_signal, y fallo de red |
| `retry_pending()` | Reintenta todos los payloads en `pending_signals.json` |
| `_post(payload, headers)` | Lógica de reintento con backoff exponencial |
| `_save_to_pending(payload)` | Agrega a `state/pending_signals.json` (solo para payloads pending, no no_signal) |

**Comportamiento por respuesta de bot1:**

| Respuesta | Acción de agente01 |
|-----------|-------------------|
| `status="executed"` | Éxito — retorna response, cooldown activado |
| `status="rejected"` | Log + Telegram ⚠️ — no reintenta |
| `status="received_no_signal"` | Confirmación OK — no es fallo |
| `status="failed"` (agotó reintentos) | Guarda en `pending_signals.json` — Telegram ❌ |
| HTTP 4xx | Log error — no reintenta |

**Backoff:** 5s → 10s → 15s entre intentos (3 máximo).

---

## sender/telegram_notifier.py

Alertas opcionales a Telegram. Si `TELEGRAM_BOT_TOKEN` o `TELEGRAM_CHAT_ID` están vacíos → no-op (sin error).

| Función | Cuándo | Mensaje |
|---------|--------|---------|
| `signal_sent(symbol, action, confidence, size)` | APPROVE ejecutado | ✅ Señal enviada |
| `signal_rejected(symbol, action, reason)` | bot1 rechaza | ⚠️ Rechazada + razón |
| `webhook_failed(symbol, error)` | 3 intentos agotados | ❌ En cola pendiente |
| `no_signal_cycle(summary)` | Ciclo sin aprobados | 🔍 Scores de todos los símbolos |
