# Fuentes de Datos — agente01 (SPY Specialist)

El único objetivo de agente01 es **investigar** y **decidir**. No ejecuta órdenes directamente. Todo su trabajo consiste en alimentarse de 12+ fuentes externas, procesarlas en 6 dimensiones, y producir una señal estructurada que bot1 puede ejecutar.

Este documento detalla exactamente de dónde viene cada dato, qué se extrae, y cómo contribuye a la decisión final.

---

## Mapa de fuentes → 6 dimensiones → decisión

```
 FUENTE EXTERNA                    DIMENSIÓN             PESO
 ──────────────────────────────────────────────────────────────────────────────
 FRED API                     →   1. Macro              25%
   CPI, PCE, NFP, Fed Funds,
   yield curve (2Y–10Y spread)
 ──────────────────────────────────────────────────────────────────────────────
 yfinance multi-TF (1D/4H/1H) →   2. Técnico            20%
   RSI, MACD, BB, SMA200
 ──────────────────────────────────────────────────────────────────────────────
 yahooquery (top-10 SPY)      →   3. Componentes        20%
 11 sectores SPDR (XLK, XLF…)
 ──────────────────────────────────────────────────────────────────────────────
 VIX term structure           →   4. Sentimiento        15%
 Put/Call ratio CBOE
 CNN Fear & Greed
 VADER (NewsAPI titulares)
 ──────────────────────────────────────────────────────────────────────────────
 FOMC calendar                →   5. Eventos            10%
 Reuters RSS geopolítica
 Economic calendar
 ──────────────────────────────────────────────────────────────────────────────
 DXY, TLT, HYG, QQQ,         →   6. Cross-Assets       10%
 GLD, USO, BTC (vs SPY)
 ──────────────────────────────────────────────────────────────────────────────
                                   SCORE TOTAL (0–1)
                                         │
                              ┌──────────┴──────────┐
                              │  Pipeline filtros   │
                              │  Paso 1: Vetos duros│
                              │  Paso 2: Score ≥0.72│
                              │  Paso 3: Mult. soft │
                              │  Paso 4: Gate dims  │
                              │  Paso 5: Claude AI  │
                              └──────────┬──────────┘
                                         │
                                  APPROVE / NO_SIGNAL
                                         │
                          POST http://127.0.0.1:8000/webhook/bot2
```

---

## Dimensión 1 — Macro (25%): FRED API

**Módulo:** `research/macro/fred_client.py`
**API:** Federal Reserve Economic Data (api.stlouisfed.org)
**API Key:** `FRED_API_KEY` (gratuita, cuenta en fred.stlouisfed.org)
**Coste:** Gratuito, sin límite práctico

### Series consultadas

| Serie FRED | Significado | Señal favorable |
|---|---|---|
| `CPIAUCSL` | CPI (inflación) yoy | CPI cayendo o estable |
| `PCEPI` | PCE (medida preferida Fed) | PCE < 2.5% |
| `PAYEMS` | Non-Farm Payrolls | NFP positivo |
| `FEDFUNDS` | Fed Funds Rate | Estabilización o bajada |
| `DGS2` | Yield 2 años | Para spread con 10Y |
| `DGS10` | Yield 10 años | Curva positiva favorable |

### Señal clave: Yield Curve

```
spread = DGS10 - DGS2
spread > 0        → curva normal      → favorable
spread > -0.50%   → inversión leve   → neutral
spread < -0.50%   → inversión fuerte → desfavorable (veto duro si macro_score < 0.35)
```

### Cómo contribuye al score

```
macro_score: combinación ponderada de:
  - CPI trend (bajando = positivo)
  - PCE vs target Fed (2%)
  - NFP momentum
  - Fed rate direction (pausa/baja = positivo)
  - Yield curve spread
```

---

## Dimensión 2 — Técnico (20%): yfinance Multi-Timeframe

**Módulo:** `research/technical/multi_tf.py`
**Librería:** `yfinance` + `ta` (Technical Analysis library)
**API Key:** No requerida
**Coste:** Gratuito

### Timeframes analizados

| Timeframe | Propósito |
|---|---|
| **1D** (diario) | Tendencia de fondo, SMA200, RSI diario |
| **4H** (4 horas) | Momentum intermedio, MACD |
| **1H** (1 hora) | Señales de entrada, detección de reversiones |

### Indicadores calculados

| Indicador | Señal favorable |
|---|---|
| RSI (1D) | 40–70 (ni sobrecomprado ni sobrevendido) |
| MACD (4H) | Línea MACD > Signal, histograma positivo |
| Bollinger Bands (1H) | Precio en banda media–superior |
| SMA200 (1D) | Precio > SMA200 (régimen alcista) |

### Conteo de timeframes bullish

```
bullish_count = número de timeframes con señal alcista (0–3)
  3/3 → technical_score muy alto
  2/3 → técnico favorable
  1/3 → técnico mixto
  0/3 → técnico bajista
```

### Veto duro relacionado

```
RSI diario > 75 → NO_SIGNAL inmediato (sobrecomprado extremo)
Precio < SMA200  → NO_SIGNAL inmediato (régimen bajista)
```

---

## Dimensión 3 — Componentes (20%): Holdings y Sectores SPY

**Módulo:** `research/components/spy_holdings.py`
**Librería:** `yahooquery`
**API Key:** No requerida
**Coste:** Gratuito

### Top-10 holdings SPY monitoreados

AAPL, MSFT, NVDA, AMZN, META, GOOGL, GOOG, TSLA, BRK.B, UNH

Para cada holding se evalúa su performance relativa. Si ≥ 3 de los top-10 reportan earnings en 48h → veto duro.

### 11 sectores SPDR

XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLB, XLC

```
sector_breadth = % de sectores con performance positiva
sector_score = sector_breadth como score 0–1
```

### Cómo contribuye al score

```
components_score = 0.6 × top10_score + 0.4 × sector_score
  top10_score = % holdings alcistas ponderado por peso en SPY
  sector_score = breadth de sectores positivos
```

---

## Dimensión 4 — Sentimiento (15%): Sentimiento Avanzado

Esta dimensión combina 4 sub-fuentes:

### 4a — VIX Term Structure

**Módulo:** `research/sentiment/vix_term_structure.py`
**Fuente:** CBOE (VX futuros via yfinance)

El VIX spot vs. futuros VX1 (1 mes) y VX2 (2 meses) indica si el mercado anticipa más o menos volatilidad:

| Estructura | Relación | Score | Interpretación |
|---|---|---|---|
| Contango | VX1 > VIX spot | **0.85** | Mercado calmado, sin miedo extremo |
| Flat | VX1 ≈ VIX spot | **0.55** | Neutral |
| Backwardation | VX1 < VIX spot | **0.20** | Pánico spot > futuro, señal de estrés |

### 4b — Put/Call Ratio CBOE

**Módulo:** `research/sentiment/put_call.py`
**Fuente:** CBOE (cboe.com/data)

```
put_call_ratio < 0.7  → mercado alcista (más calls que puts) → favorable
put_call_ratio 0.7–1.0 → neutral
put_call_ratio > 1.0  → pesimismo / cobertura bajista → desfavorable
```

### 4c — CNN Fear & Greed Index

**Endpoint:** CNN Business (endpoint público)
**Fallback:** 50.0 (Neutral) si hay error 418 anti-bot

```
score 0–100 normalizado → 0.0–1.0 en sentiment_score
  75–100 (Extreme Greed) → 0.75–1.0
  55–74  (Greed)         → 0.55–0.74
  45–54  (Neutral)       → 0.45–0.54
  25–44  (Fear)          → 0.25–0.44
  0–24   (Extreme Fear)  → 0.00–0.24
```

### 4d — VADER NLP sobre noticias SPY

**Módulo:** `research/news_fetcher.py` + `analysis/sentiment_analyzer.py`
**Fuente:** NewsAPI.org (100 req/día plan free)
**Librería:** `vaderSentiment` (corre localmente)

```
headline_sentiment = promedio compound VADER de titulares SPY (últimas 4h)
compound normalizado: (compound + 1) / 2 → 0.0–1.0
```

### Combinación de las 4 sub-fuentes

```
sentiment_score = 0.30×vix_term + 0.25×put_call + 0.25×fear_greed + 0.20×vader
```

---

## Dimensión 5 — Eventos (10%): Calendario Económico

**Módulo:** `research/events/event_calendar.py`
**Fuentes:** fed.gov (FOMC) + Reuters RSS + Trading Economics

### Tipos de eventos monitoreados

| Evento | Impacto | Condición veto |
|---|---|---|
| Reunión FOMC | EXTREME | Fecha < 24h → veto duro |
| CPI, NFP, PCE release | HIGH | < 24h → multiplicador ×0.85 |
| Geopolítica mayor (Reuters) | EXTREME/HIGH | < 12h → veto directo |

### Multiplicadores de score

```
Sin eventos de impacto próximos → multiplicador = 1.0  (sin cambio)
Evento HIGH < 24h               → multiplicador = 0.85 (penaliza score)
Evento EXTREME < 12h            → veto directo → NO_SIGNAL
```

### El trail también se ajusta

```
Si hay evento HIGH < 24h: trail_percent × 0.70 (más ajustado = más defensivo)
```

---

## Dimensión 6 — Cross-Assets (10%): Divergencias vs SPY

**Módulo:** `research/cross_asset/cross_asset.py`
**Fuente:** yfinance

### Activos monitoreados

| Ticker | Activo | Relación esperada con SPY |
|---|---|---|
| `DX-Y.NYB` | DXY (Dólar) | Inversa — DXY sube → SPY presionado |
| `TLT` | Bonos 20Y | Inversa — TLT baja (yields suben) → presión SPY |
| `HYG` | High Yield Bonds | Directa — HYG sube = apetito riesgo |
| `QQQ` | Nasdaq 100 | Directa — QQQ lidera = favorable SPY |
| `GLD` | Oro | Neutral/inversa — GLD sube fuerte = refugio = bearish |
| `USO` | Petróleo | Contextual |
| `BTC-USD` | Bitcoin | Directa en risk-on — BTC sube = apetito riesgo |

### Cómo se calcula

```
Para cada activo: cambio % reciente vs. correlación histórica esperada con SPY
cross_asset_score = promedio de señales de confirmación/divergencia
  Confirmación: activo se mueve en línea con expectativa → suma
  Divergencia:  activo contradice expectativa → resta
```

---

## Resumen: Cómo se Combinan las 6 Dimensiones

### Fórmula del Score Total

```
TOTAL = macro×0.25 + técnico×0.20 + componentes×0.20
      + sentimiento×0.15 + eventos×0.10 + cross_assets×0.10
```

### Gate de Aprobación (Paso 4 del pipeline)

```
score × multiplicador_eventos >= 0.72
AND
dimensiones con score > 0.55  >=  5 de 6
```

### Validación Claude AI (Paso 5)

Claude recibe todo el snapshot de mercado + scores de cada dimensión y puede:
- **Confirmar APPROVE** → lo más frecuente si el filtro pasó
- **Vetar la señal** → override a NO_SIGNAL si detecta inconsistencias narrativas
- **Refinar el trail** → ajuste dentro del rango permitido por VIX régimen

Claude NO puede promover NO_SIGNAL a APPROVE (los filtros son autoritativos en rechazos).

---

## Resiliencia y Fallbacks

| Fuente | Fallo posible | Fallback |
|---|---|---|
| FRED API | Sin key, timeout | Macro score = 0.5 (neutral) |
| yfinance multi-TF | Rate limit | Score técnico = 0.5, bullish_count = 1 |
| yahooquery holdings | Timeout | Components score = 0.5 |
| VIX term structure | Futuros no disponibles | Estructura = "flat" (score 0.55) |
| Put/Call CBOE | Endpoint caído | Put/Call = 0.85 (neutral) |
| CNN Fear & Greed | Error 418 anti-bot | Score = 50.0 (Neutral → 0.50) |
| NewsAPI | Sin key / cuota agotada | Lista vacía → sentiment = neutral |
| VADER | — (corre local) | — |
| FOMC calendar | Parsing error | Sin eventos detectados |
| Reuters RSS | Timeout | Sin eventos geopolíticos |
| Cross-asset | yfinance rate limit | Score = 0.5 por activo fallido |
| Claude AI | API error, timeout | APPROVE pasa sin veto (filtros ya lo validaron) |

Ningún fallo individual detiene el ciclo. El agente siempre produce una decisión.
