# Fuentes de Datos — agente01

El único objetivo de agente01 es **investigar** y **decidir**. No ejecuta órdenes directamente: todo su trabajo consiste en alimentarse de fuentes externas, procesar esa información, y producir una señal estructurada que bot1 puede ejecutar.

Este documento detalla exactamente de dónde viene cada dato, qué se extrae, y cómo contribuye a la decisión final.

---

## Mapa de fuentes → decisión

```
 FUENTE EXTERNA                DATO EXTRAÍDO            CONTRIBUCIÓN AL SCORE
 ─────────────────────────────────────────────────────────────────────────────

 Yahoo Finance (precio)   →   precio, SMA20, volumen  →  trend_score   (30%)
 ─────────────────────────────────────────────────────────────────────────────
 NewsAPI.org (titulares)  →   headlines últimas 6h     →
                                   │                        sentiment_score (30%)
 VADER NLP (local)        ←────────┘  analiza texto    →
 ─────────────────────────────────────────────────────────────────────────────
 CNN Fear & Greed         →   índice de sentimiento    →  macro_score   (25%)
                              del mercado (0–100)
 ─────────────────────────────────────────────────────────────────────────────
 Yahoo Finance (^VIX)     →   volatilidad implícita    →  news_score    (15%)
                              del mercado
 ─────────────────────────────────────────────────────────────────────────────
                                                             TOTAL SCORE (0–1)
                                                                   │
                                                         ¿≥ MIN_CONFIDENCE?
                                                         ¿≥ 2/3 señales alineadas?
                                                                   │
                                                              APPROVE / NO_SIGNAL
                                                                   │
                                               POST http://127.0.0.1:8000/webhook/bot2
```

---

## Fuente 1 — Yahoo Finance: Precio y Tendencia

**Módulo:** `research/market_data.py`
**Librería:** `yfinance`
**API Key:** No requerida
**Coste:** Gratuito
**Límite:** Sin límite oficial, pero sujeto a rate limiting (pausas breves entre llamadas)

### Qué se descarga

Para cada símbolo del `WATCHLIST`, se descarga el historial de los **últimos 30 días** de precios de cierre y volumen.

```
Ticker("SPY").history(period="30d")
→ DataFrame con columnas: Close, Volume (30 filas)
```

### Qué se calcula

| Campo | Cálculo | Significado |
|---|---|---|
| `price` | Último cierre del día | Precio actual |
| `prev_close` | Penúltimo cierre | Precio del día anterior |
| `change_pct` | `(price - prev_close) / prev_close × 100` | % de cambio diario |
| `volume` | Volumen del último día | Actividad del día |
| `avg_volume` | Media de volumen de los 30 días | Volumen normal |
| `volume_ratio` | `volume / avg_volume` | Anomalía de volumen (>1 = más activo de lo normal) |
| `sma20` | Media simple de los últimos 20 cierres | Tendencia de medio plazo |
| `price_vs_sma20` | `(price - sma20) / sma20 × 100` | % por encima/debajo de la media |
| `trend` | Ver lógica abajo | Dirección de la tendencia |

### Lógica de clasificación de tendencia

```
price_vs_sma20 > +1%  →  trend = "bullish"
price_vs_sma20 < -1%  →  trend = "bearish"
entre -1% y +1%       →  trend = "neutral"
```

### Cómo contribuye al score

```
trend_score (peso 30%):
  "bullish" → 1.0
  "neutral" → 0.5
  "bearish" → 0.0
  + vol_bonus: si volume_ratio > 1.0 → se suma hasta +0.10
               (cuanto más volumen anómalo, más convicción en la tendencia)
```

**Ejemplo real:**
```
SPY: $715.17 | SMA20: $685.04 | price_vs_sma20: +4.40%
→ trend = "bullish"
→ trend_score = 1.0 + vol_bonus(0.0) = 1.0
→ contribución al score: 1.0 × 30% = 0.300
```

---

## Fuente 2 — NewsAPI: Titulares de Prensa Financiera

**Módulo:** `research/news_fetcher.py`
**Endpoint:** `https://newsapi.org/v2/everything`
**API Key:** **Requerida** (variable `NEWSAPI_KEY`)
**Coste:** Gratuito (100 requests/día en plan free)
**Consumo real:** ~2 requests/ciclo (uno por símbolo). Con 2 símbolos y ciclos de 4h = ~12 requests/día.

### Qué se consulta

Por cada símbolo, se buscan artículos publicados en las **últimas 6 horas** (configurable con el parámetro `hours`):

```
GET /v2/everything
  ?q=SPY
  &language=en
  &sortBy=publishedAt
  &apiKey=...
```

### Qué se extrae

Por cada artículo devuelto:

| Campo | Fuente | Ejemplo |
|---|---|---|
| `title` | `article["title"]` | "Fed signals pause in rate hikes" |
| `description` | `article["description"]` | "The Federal Reserve indicated..." |
| `source` | `article["source"]["name"]` | "Reuters" |
| `published_at` | `article["publishedAt"]` | "2026-04-27T13:45:00Z" |

Solo se incluyen artículos cuyo `published_at` está dentro de la ventana de tiempo. La lista puede estar vacía si no hay noticias recientes (común fuera del horario de mercado).

### Qué pasa con los titulares (paso siguiente: VADER)

Los titulares por sí solos no valen como número. El siguiente paso (fuente 3) los convierte en una señal cuantitativa.

---

## Fuente 3 — VADER: Análisis de Sentimiento NLP

**Módulo:** `analysis/sentiment_analyzer.py`
**Librería:** `vaderSentiment` (corre localmente)
**API Key:** No requerida
**Coste:** Gratuito, sin límite

VADER (Valence Aware Dictionary for sEntiment Reasoning) es un modelo de análisis de sentimiento especializado en texto financiero y de redes sociales. Asigna un **score compound** entre -1.0 y +1.0 a cada frase.

### Qué se analiza

Para cada titular de NewsAPI, VADER evalúa:
- Palabras positivas: "surge", "rally", "bullish", "beat expectations"
- Palabras negativas: "crash", "decline", "bearish", "miss", "recession"
- Intensificadores: "very", "extremely", "significantly"
- Puntuación y mayúsculas como señales de énfasis

### Qué se produce

```python
analyze(headlines) → SentimentResult:
  compound        = promedio de scores compound de todos los titulares
  positive_ratio  = % de titulares con compound ≥ +0.05
  negative_ratio  = % de titulares con compound ≤ -0.05
  headline_count  = total de titulares analizados
  label           = "positive" | "neutral" | "negative"
```

**Clasificación del label:**
```
compound ≥ +0.05  →  "positive"
compound ≤ -0.05  →  "negative"
entre -0.05/+0.05 →  "neutral"
```

**Con 0 titulares:** retorna compound=0.0, label="neutral". No genera error — el ciclo continúa con sentimiento neutral.

### Cómo contribuye al score

```
sentiment_score (peso 30%):
  normalización: (compound + 1) / 2  →  convierte rango [-1,+1] a [0,1]

  compound = +0.80  →  sentiment_score = 0.90  (muy positivo)
  compound = +0.10  →  sentiment_score = 0.55  (levemente positivo)
  compound =  0.00  →  sentiment_score = 0.50  (neutral)
  compound = -0.50  →  sentiment_score = 0.25  (negativo)
```

**Ejemplo real:**
```
8 titulares: "Fed signals pause", "SPY breaks resistance", "Markets rally on earnings"
→ compound promedio = +0.68
→ sentiment_score = (0.68 + 1) / 2 = 0.84
→ contribución al score: 0.84 × 30% = 0.252
```

---

## Fuente 4 — CNN Fear & Greed Index: Sentimiento Macro del Mercado

**Módulo:** `research/macro_indicators.py`
**Endpoint:** `https://production.dataviz.cnn.io/index/fearandgreed/graphdata`
**API Key:** No requerida (endpoint público de CNN)
**Coste:** Gratuito
**Fallback:** Si el endpoint bloquea (error 418 anti-bot), se usa 50.0 (Neutral)

### Qué mide

El Fear & Greed Index de CNN es un índice compuesto que mide el **sentimiento general del mercado** en una escala de 0 a 100, combinando 7 indicadores internamente:

| Zona | Score | Interpretación |
|---|---|---|
| Extreme Fear | 0–24 | Pánico generalizado, posible suelo |
| Fear | 25–44 | Pesimismo, cautela |
| Neutral | 45–55 | Sin dirección clara |
| Greed | 56–74 | Optimismo, apetito por riesgo |
| Extreme Greed | 75–100 | Euforia, posible techo |

### Qué se extrae

```
fear_greed_score  →  valor numérico 0–100
fear_greed_label  →  "Extreme Fear" | "Fear" | "Neutral" | "Greed" | "Extreme Greed"
```

### Cómo contribuye al score

```
macro_score (peso 25%):
  fear_greed_score / 100  →  normaliza 0–100 a 0.0–1.0

  score = 72  →  macro_score = 0.72  (Greed → bullish)
  score = 50  →  macro_score = 0.50  (Neutral)
  score = 30  →  macro_score = 0.30  (Fear → bearish)
```

### También determina el macro_bias

El `macro_bias` es una señal cualitativa que el motor de decisión usa para el consenso 2/3:

```
macro_bias = "bullish"  si fear_greed ≥ 60 O vix < 20
macro_bias = "bearish"  si fear_greed ≤ 40 O vix > 25
macro_bias = "neutral"  en el resto de los casos
```

---

## Fuente 5 — Yahoo Finance: VIX (Volatilidad del Mercado)

**Módulo:** `research/macro_indicators.py`
**Ticker:** `^VIX` (CBOE Volatility Index)
**API Key:** No requerida
**Coste:** Gratuito
**Fallback:** 20.0 si no está disponible

### Qué mide

El VIX mide la **volatilidad implícita** del S&P 500 para los próximos 30 días, derivada de los precios de opciones. Es conocido como el "índice del miedo" del mercado:

| Régimen | VIX | Interpretación |
|---|---|---|
| `low` | < 15 | Calma total, baja volatilidad → favorable para trading |
| `moderate` | 15–20 | Normalidad → condiciones aceptables |
| `high` | 20–30 | Volatilidad elevada → precaución |
| `extreme` | > 30 | Crisis / pánico → señal muy desfavorable |

### Cómo contribuye al score

```
news_score (peso 15%):
  "low"     (VIX < 15)   →  1.00  (entorno ideal)
  "moderate"(VIX 15–20)  →  0.65  (aceptable)
  "high"    (VIX 20–30)  →  0.30  (desfavorable)
  "extreme" (VIX > 30)   →  0.00  (no operar)
```

**Ejemplo real:**
```
VIX = 18.02  →  régimen "moderate"  →  news_score = 0.65
→ contribución al score: 0.65 × 15% = 0.098
```

---

## Cómo se combinan todas las fuentes

### Paso 1 — Score numérico compuesto

```
TOTAL = (sentiment_score × 0.30)
      + (trend_score     × 0.30)
      + (macro_score     × 0.25)
      + (news_score      × 0.15)

Rango: 0.0 (todo negativo) → 1.0 (todo perfecto)
```

### Paso 2 — Umbral mínimo

```
TOTAL < MIN_CONFIDENCE (default: 0.65)  →  NO_SIGNAL inmediato
```

### Paso 3 — Consenso de señales (regla 2/3)

Aunque el score supere el umbral, se requiere que **al menos 2 de 3 señales cualitativas** apunten en la misma dirección:

```
Señal 1: trend      → "bullish" | "neutral" | "bearish"
Señal 2: sentiment  → "positive"(bullish) | "neutral" | "negative"(bearish)
Señal 3: macro_bias → "bullish" | "neutral" | "bearish"

≥ 2 bullish  →  APPROVE BUY
≥ 2 bearish  →  NO_SIGNAL (no se hacen operaciones cortas)
mixto        →  NO_SIGNAL
```

### Paso 4 — Tamaño de posición por confianza

```
TOTAL ≥ 0.85  →  size = 0.15  (15% del portafolio)
TOTAL ≥ 0.75  →  size = 0.10  (10%)
TOTAL ≥ 0.65  →  size = 0.05  (5%)
```

---

## Ejemplo completo de una decisión APPROVE

```
Fecha: 2026-04-27 | Símbolo: SPY

FUENTE 1 — Yahoo Finance (precio)
  precio:        $715.17
  SMA20:         $685.04
  price_vs_sma20: +4.40%  →  trend = "bullish"
  volume_ratio:   0.42x   →  vol_bonus = 0
  → trend_score = 1.0

FUENTE 2+3 — NewsAPI + VADER
  titulares:     0 en últimas 6h (fuera de horario)
  compound:      0.0  →  label = "neutral"
  → sentiment_score = (0.0 + 1) / 2 = 0.50

FUENTE 4 — CNN Fear & Greed
  score:         50.0  →  label = "Neutral" (fallback)
  macro_bias:    "bullish"  (VIX < 20 → condición bullish)
  → macro_score = 50 / 100 = 0.50

FUENTE 5 — VIX
  VIX:           18.02  →  régimen "moderate"
  → news_score = 0.65

SCORE TOTAL:
  (0.50 × 0.30) + (1.0 × 0.30) + (0.50 × 0.25) + (0.65 × 0.15)
= 0.150 + 0.300 + 0.125 + 0.098
= 0.672

UMBRAL: 0.672 ≥ 0.65 ✓

CONSENSO:
  trend="bullish" ✓  sentiment="neutral" ✗  macro="bullish" ✓
  → 2/3 bullish → APPROVE BUY

TAMAÑO: 0.672 ≥ 0.65 → size = 0.05

RESULTADO ENVIADO A BOT1:
  action="buy" | confidence=0.672 | size=0.05
```

---

## Resiliencia y fallbacks

| Fuente | Fallo posible | Fallback |
|---|---|---|
| Yahoo Finance (precio) | Rate limit, símbolo inválido | `None` → símbolo saltado ese ciclo |
| Yahoo Finance (^VIX) | Rate limit | VIX = 20.0 (moderate) |
| CNN Fear & Greed | Error 418 (anti-bot) | score = 50.0 (Neutral) |
| NewsAPI | Sin key, sin cuota, sin resultados | Lista vacía → sentiment neutral |
| VADER | — (corre local, sin dependencia externa) | — |

Ningún fallo individual detiene el ciclo. El agente siempre produce una decisión, aunque sea con datos parciales.
