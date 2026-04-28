# Fuentes de Datos — agente01

El único objetivo de agente01 es **investigar** y **decidir**. No ejecuta órdenes directamente: todo su trabajo consiste en alimentarse de fuentes externas, procesar esa información, y producir una señal estructurada que bot1 puede ejecutar.

Este documento detalla exactamente de dónde viene cada dato, qué se extrae, y cómo contribuye a la decisión final.

---

## Mapa de fuentes → decisión

```
 FUENTE EXTERNA                DATO EXTRAÍDO              CONTRIBUCIÓN AL SCORE
 ──────────────────────────────────────────────────────────────────────────────

 Yahoo Finance (precio)   →   precio, SMA20, SMA50,    →  trend_score   (40%)
                               volumen, trend_strength
 ──────────────────────────────────────────────────────────────────────────────
 NewsAPI.org (titulares)  →   headlines ultimas 4h      →
                                   │                        sentiment_score (20%)
 VADER NLP (local)        <────────┘  analiza texto     →
 ──────────────────────────────────────────────────────────────────────────────
 CNN Fear & Greed         →   indice de sentimiento     →  macro_score   (25%)
                               del mercado (0–100)
 ──────────────────────────────────────────────────────────────────────────────
 Yahoo Finance (^VIX)     →   volatilidad implicita     →  vix_score     (15%)
                               del mercado
 ──────────────────────────────────────────────────────────────────────────────
                                                              TOTAL SCORE (0–1)
                                                                    │
                                                          >= MIN_CONFIDENCE (0.70)?
                                                          >= 3/3 señales alineadas?
                                                          VIX != "extreme"?
                                                                    │
                                                             APPROVE / NO_SIGNAL
                                                                    │
                                                POST http://127.0.0.1:8000/webhook/bot2
```

---

## Fuente 1 — Yahoo Finance: Precio, SMA20, SMA50 y Tendencia

**Módulo:** `research/market_data.py`
**Librería:** `yfinance`
**API Key:** No requerida
**Coste:** Gratuito
**Limite:** Sin limite oficial, sujeto a rate limiting (pausas breves entre llamadas)

### Qué se descarga

Para cada símbolo del `WATCHLIST`, se descarga el historial de los **últimos 60 días** de precios de cierre y volumen.

```
Ticker("SPY").history(period="60d")
→ DataFrame con columnas: Close, Volume (60 filas)
```

### Qué se calcula

| Campo | Cálculo | Significado |
|---|---|---|
| `price` | Último cierre del día | Precio actual |
| `prev_close` | Penúltimo cierre | Precio del día anterior |
| `change_pct` | `(price - prev_close) / prev_close × 100` | % de cambio diario |
| `volume` | Volumen del último día | Actividad del día |
| `avg_volume` | Media de volumen de los 60 días | Volumen normal |
| `volume_ratio` | `volume / avg_volume` | Anomalía de volumen (>1 = más activo de lo normal) |
| `sma20` | Media simple de los últimos 20 cierres | Tendencia de medio plazo |
| `sma50` | Media simple de los últimos 50 cierres | Tendencia de largo plazo |
| `price_vs_sma20` | `(price - sma20) / sma20 × 100` | % por encima/debajo de la media |
| `trend` | "bullish" / "neutral" / "bearish" | Clasificación simple |
| `trend_strength` | Ver tabla abajo | Clasificación detallada (5 niveles) |

### Lógica de trend_strength (usa SMA20 y SMA50)

La estrategia swing usa `trend_strength` — una clasificación de 5 niveles que considera la alineación entre precio, SMA20 y SMA50:

| trend_strength | Condición | Score base |
|---|---|---|
| `strong_bullish` | precio > SMA20 > SMA50 | 1.00 |
| `bullish` | precio > SMA20, SMA20 aprox. SMA50 | 0.75 |
| `neutral` | precio aprox. SMA20 | 0.50 |
| `bearish` | precio < SMA20 | 0.25 |
| `strong_bearish` | precio < SMA20 < SMA50 | 0.00 |

La `trend` simple se deriva de `price_vs_sma20`:
```
price_vs_sma20 > +1%  →  trend = "bullish"
price_vs_sma20 < -1%  →  trend = "bearish"
entre -1% y +1%       →  trend = "neutral"
```

### Cómo contribuye al score

```
trend_score (peso 40%):
  base = strength_map[trend_strength]   # 0.0 – 1.0
  vol_bonus = min((volume_ratio - 1.0) × 0.1, 0.10) si volume_ratio > 1.0
  trend_score = min(base + vol_bonus, 1.0)
```

**Ejemplo real:**
```
SPY: $590.00 | SMA20=$572.00 | SMA50=$555.00
precio > SMA20 > SMA50  →  trend_strength = "strong_bullish"
→ trend_score = 1.0
volume_ratio = 1.2x  →  vol_bonus = 0.02
→ trend_score final = 1.0 (ya en máximo)
→ contribución al score: 1.0 × 40% = 0.400
```

---

## Fuente 2 — NewsAPI: Titulares de Prensa Financiera

**Módulo:** `research/news_fetcher.py`
**Endpoint:** `https://newsapi.org/v2/everything`
**API Key:** **Requerida** (variable `NEWSAPI_KEY`)
**Coste:** Gratuito (100 requests/día en plan free)
**Consumo real:** ~8 requests/ciclo (uno por símbolo). Con 8 símbolos y ciclos de 1h = hasta 64 requests/hora durante mercado (6.5h) = hasta 416/día. Si alcanza el límite, la lista queda vacía y el sentimiento es neutral.

### Qué se consulta

Por cada símbolo, se buscan artículos publicados en las **últimas 4 horas** (alineado al ciclo de 1h):

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

Solo se incluyen artículos cuyo `published_at` está dentro de la ventana de 4 horas. La lista puede estar vacía si no hay noticias recientes (el ciclo continúa con sentimiento neutral).

### Qué pasa con los titulares

Los titulares por sí solos no valen como número. El siguiente paso (Fuente 3) los convierte en una señal cuantitativa.

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
  positive_ratio  = % de titulares con compound >= +0.05
  negative_ratio  = % de titulares con compound <= -0.05
  headline_count  = total de titulares analizados
  label           = "positive" | "neutral" | "negative"
```

**Clasificación del label:**
```
compound >= +0.05  →  "positive"
compound <= -0.05  →  "negative"
entre -0.05/+0.05 →  "neutral"
```

**Con 0 titulares:** retorna compound=0.0, label="neutral". No genera error.

### Cómo contribuye al score

```
sentiment_score (peso 20%):
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
→ contribución al score: 0.84 × 20% = 0.168
```

### Importancia en la decisión de consenso

Además del score numérico, el `label` de sentimiento participa en la **regla de consenso 3/3**:
- `label == "positive"` cuenta como señal bullish
- `label == "negative"` cuenta como señal bearish
- `label == "neutral"` no suma ni resta al consenso

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

El `macro_bias` es una señal cualitativa que el motor de decisión usa para el consenso 3/3:

```
Puntos bullish:   +1 si fear_greed >= 60  |  +1 si vix < 20
Puntos bearish:   +1 si fear_greed <= 40  |  +1 si vix > 25

macro_bias = "bullish" si puntos_bullish > puntos_bearish
macro_bias = "bearish" si puntos_bearish > puntos_bullish
macro_bias = "neutral" si empate
```

---

## Fuente 5 — Yahoo Finance: VIX (Volatilidad del Mercado)

**Módulo:** `research/macro_indicators.py`
**Ticker:** `^VIX` (CBOE Volatility Index)
**API Key:** No requerida
**Coste:** Gratuito
**Fallback:** 20.0 si no está disponible

### Qué mide

El VIX mide la **volatilidad implícita** del S&P 500 para los próximos 30 días. Es el "índice del miedo" del mercado.

### Régimen VIX — el parámetro más importante de la estrategia

El VIX no solo contribuye al score numérico: **determina el trailing stop y el tiempo máximo de la posición**:

| Régimen | VIX | trail_percent | take_profit | max_holding_days |
|---|---|---|---|---|
| `low` | < 15 | **3.0%** | null (sin TP, dejar correr) | 15 días |
| `moderate` | 15–20 | **4.0%** | null | 10 días |
| `high` | 20–30 | **5.5%** | **8.0%** (defensivo) | 7 días |
| `extreme` | > 30 | — | — | **No abrir** |

**Razón:** un trailing del 3% con VIX en 25 te saca con cualquier vela normal. La volatilidad dicta el espacio que necesita el trade para respirar.

### Cómo contribuye al score

```
vix_score (peso 15%):
  "low"      (VIX < 15)   →  1.00  (entorno ideal)
  "moderate" (VIX 15–20)  →  0.65  (aceptable)
  "high"     (VIX 20–30)  →  0.30  (desfavorable)
  "extreme"  (VIX > 30)   →  0.00  (no operar)
```

### Bloqueo por VIX extremo

Si `vix_regime == "extreme"`, **no se abren nuevas posiciones independientemente del score**. Es la Regla 0 del motor de decisión.

**Ejemplo real:**
```
VIX = 18.02  →  régimen "moderate"  →  vix_score = 0.65
→ contribución al score: 0.65 × 15% = 0.098
→ trail_percent para la posición = 4.0%
```

---

## Cómo se combinan todas las fuentes

### Paso 1 — Score numérico compuesto

```
TOTAL = (trend_score     × 40%)
      + (sentiment_score × 20%)
      + (macro_score     × 25%)
      + (vix_score       × 15%)

Rango: 0.0 (todo negativo) → 1.0 (todo perfecto)
```

### Paso 2 — Bloqueo por VIX extremo (Regla 0)

```
vix_regime == "extreme"  →  NO_SIGNAL inmediato (sin analizar el score)
```

### Paso 3 — Umbral mínimo (Regla 1)

```
TOTAL < MIN_CONFIDENCE (0.70)  →  NO_SIGNAL inmediato
```

### Paso 4 — Consenso de señales 3/3 (Regla 2)

Se requiere que **las 3 señales cualitativas** apunten a bullish:

```
Señal 1: trend_strength  → "bullish" o "strong_bullish"  (quote.trend == "bullish")
Señal 2: sentiment       → "positive"
Señal 3: macro_bias      → "bullish"

3/3 bullish  →  APPROVE BUY
Cualquier fallo → NO_SIGNAL
```

### Paso 5 — Tamaño de posición por confianza

```
TOTAL >= 0.85  →  size = 8%  (SIZE_HIGH_CONFIDENCE)
TOTAL >= 0.78  →  size = 5%  (SIZE_MEDIUM_CONFIDENCE)
TOTAL >= 0.70  →  size = 3%  (SIZE_LOW_CONFIDENCE)
```

### Paso 6 — Trailing stop dinámico

El `trail_percent` se determina por el régimen VIX **al momento de apertura** (no cambia durante la vida de la posición).

---

## Ejemplo completo de una decisión APPROVE

```
Fecha: 2026-04-27 | Símbolo: SPY | VIX = 16.5 (moderate)

FUENTE 1 — Yahoo Finance (precio, 60 días de historia)
  precio:        $590.00
  SMA20:         $572.00
  SMA50:         $555.00
  price > SMA20 > SMA50  →  trend_strength = "strong_bullish"
  volume_ratio:  1.1x    →  vol_bonus = 0.01
  → trend_score = min(1.0 + 0.01, 1.0) = 1.0

FUENTE 2+3 — NewsAPI + VADER (ultimas 4h)
  titulares:     6 articulos
  compound:      +0.52  →  label = "positive"
  → sentiment_score = (0.52 + 1) / 2 = 0.76

FUENTE 4 — CNN Fear & Greed
  score:         65  →  label = "Greed"
  macro_bias:    "bullish"  (F&G >= 60 → +1 bullish, VIX<20 → +1 bullish)
  → macro_score = 65 / 100 = 0.65

FUENTE 5 — VIX
  VIX: 16.5  →  régimen "moderate"
  → vix_score = 0.65
  → trail_percent para esta posición = 4.0%

SCORE TOTAL:
  (1.0 × 40%) + (0.76 × 20%) + (0.65 × 25%) + (0.65 × 15%)
= 0.400 + 0.152 + 0.163 + 0.098
= 0.813

REGLA 0: VIX != extreme ✓
UMBRAL:  0.813 >= 0.70 ✓
CONSENSO:
  trend=strong_bullish → "bullish" ✓
  sentiment=positive ✓
  macro=bullish ✓
  → 3/3 → APPROVE BUY

TAMAÑO: 0.813 >= 0.78 → size = 5%
TRAILING: moderate → trail_percent = 4.0%

RESULTADO ENVIADO A BOT1:
  action="buy" | confidence=0.813 | size=0.05 | trail_percent=4.0
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
