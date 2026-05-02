# agente01 — SPY Specialist: Investigación Financiera Autónoma

## Visión General

agente01 es un **especialista exclusivo en SPY** (S&P 500 ETF). Investiga el mercado desde 6 dimensiones de análisis, aplica un pipeline de filtros en cascada, y usa **Claude AI** como motor de decisión final. El resultado es siempre binario: `APPROVE` (swing long SPY) o `NO_SIGNAL`.

El agente investiga y decide. bot1 y Alpaca manejan la ejecución y el trailing stop.

```
agente01 (investigación + decisión — SPY únicamente)
    │
    └──► POST http://127.0.0.1:8000/webhook/bot2 ──► bot1 (Trading-bot) ──► Alpaca
```

Ambos bots corren en la misma PC y se comunican directamente por `127.0.0.1`.

---

## Fuentes de Información (12+ fuentes)

| # | Dimensión | Fuentes principales | Peso |
|---|-----------|--------------------|----|
| 1 | **Macro** | FRED API (CPI, PCE, NFP, Fed Funds Rate, yield curve) | 25% |
| 2 | **Técnico** | yfinance multi-timeframe (1D / 4H / 1H): RSI, MACD, BB, SMA200 | 20% |
| 3 | **Componentes** | Top-10 holdings SPY + 11 sectores SPDR | 20% |
| 4 | **Sentimiento** | VIX term structure + Put/Call CBOE + Fear&Greed + VADER | 15% |
| 5 | **Eventos** | FOMC + calendario económico + geopolítica Reuters RSS | 10% |
| 6 | **Cross-Assets** | DXY, TLT, HYG, QQQ, GLD, USO, BTC divergencias vs SPY | 10% |

Para el detalle completo de cada fuente → ver [data_sources.md](data_sources.md).

---

## Arquitectura de Alto Nivel

```
┌────────────────────────────────────────────────────────────────────┐
│                          agente01                                  │
│                                                                    │
│  12+ FUENTES        6 DIMENSIONES        PIPELINE                  │
│  ┌──────────┐      ┌─────────────┐      ┌─────────────────────┐    │
│  │FRED API  │─────►│ 1. Macro    │─────►│ Paso 1: Vetos duros │    │
│  │yfinance  │─────►│ 2. Técnico  │─────►│ Paso 2: Score 0–1   │    │
│  │yahooquery│─────►│ 3. Componen.│─────►│ Paso 3: Mult. suave │    │
│  │CBOE VIX  │─────►│ 4. Sentim.  │─────►│ Paso 4: Gate ≥0.72  │    │
│  │Reuters   │─────►│ 5. Eventos  │─────►│ Paso 5: Claude AI   │    │
│  │DXY/TLT/  │─────►│ 6. Cross-A. │─────►│  → APPROVE /        │    │
│  │HYG/GLD   │      └─────────────┘      │    NO_SIGNAL        │    │
│  └──────────┘                           └──────────┬──────────┘    │
│                                                    │               │
│                         ┌──────────────────────────────────┐       │
│  Exit Evaluator ───────►│  Webhook Sender                  │       │
│  (4 triggers de         │  127.0.0.1:8000                  │       │
│   cierre forzado)       └──────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP POST /webhook/bot2
┌────────────────────────────────────────────────────────────────────┐
│                    bot1 (Trading-bot)                              │
│              FastAPI en 127.0.0.1:8000                             │
│   Valida secret → Parsea señal → Ejecuta en Alpaca                 │
└────────────────────────────────────────────────────────────────────┘
```

---

## Estrategia: SPY Specialist con Trailing Stop Dinámico

agente01 opera bajo una estrategia de **swing trading especializada en SPY** — posiciones de varios días que capturan movimientos de momentum sostenido. El trailing stop se calibra automáticamente según el régimen de volatilidad (VIX) en el momento de apertura.

| Parámetro | Valor |
|---|---|
| Símbolo | **SPY únicamente** |
| Ciclo de investigación | Cada **60 minutos** (horario de mercado) |
| Umbral de score | **0.72** (gate de aprobación) |
| Dimensiones mínimas | **5 de 6 con score > 0.55** |
| Motor de decisión | **Claude AI (doble validación)** |
| Trailing stop | **3% / 4% / 5.5%** según régimen VIX |
| Take profit | Solo en VIX high (8%); en low/moderate se deja correr |
| Bloqueo VIX extremo | No se abren posiciones si VIX > 30 |
| Posición | Solo 1 posición SPY a la vez |

Para el detalle completo → ver [strategy.md](strategy.md).

---

## Características Principales

- **Especialización profunda en SPY**: 6 dimensiones de análisis vs. el sistema legado de 4 componentes con 8 ETFs.
- **Pipeline de filtros en cascada**: Vetos duros → Score compuesto → Multiplicadores de eventos → Gate doble (score + dimensiones) → Validación Claude AI.
- **Claude AI como motor de decisión**: El modelo recibe el snapshot completo de mercado y puede confirmar APPROVE, vetar la señal, o refinar el sizing.
- **Scoring 6 dimensiones**: macro×0.25 + técnico×0.20 + componentes×0.20 + sentimiento×0.15 + eventos×0.10 + cross_assets×0.10.
- **4 tiers de position sizing**: 8% / 12% / 18% / 25% del capital según score.
- **Trailing dinámico por VIX**: 3% (VIX bajo) / 4% (moderado) / 5.5% (alto). Sin TP fijo en VIX bajo/moderado.
- **Invalidación de tesis**: 4 triggers de cierre forzado — VIX extremo, reversión con volumen, crash de sentimiento, tiempo máximo.
- **Ciclos prioritarios**: 09:45, 12:30, 15:30 ET marcados con `[PRIORITY]` en logs.
- **Resiliencia ante fallos**: Señales no entregadas en `pending_signals.json`, reintentadas al próximo ciclo.
- **Log Excel completo**: 47 columnas incluyendo las 6 dimensiones y el razonamiento de Claude.
- **Modo DRY_RUN**: Ciclo completo sin enviar señales reales a bot1.

---

## Estructura del Proyecto

```
Trading-agente-01/
├── agente01.py               # Entry point + APScheduler
├── run_analysis.py           # Ejecución manual fuera de horario (testing)
├── excel_logger.py           # Escritura de trade_log.xlsx (una fila por ciclo)
├── config.py                 # Configuración central (carga .env)
├── .env                      # Credenciales (nunca commitear)
├── .env.example              # Plantilla de variables
├── requirements.txt          # Dependencias Python
├── start_agente01.bat        # Arranque rapido en Windows (doble click)
│
├── research/                 # Capa de investigación (12+ fuentes)
│   ├── market_data.py        # Precio, volumen, SMA via yfinance (legacy)
│   ├── macro_indicators.py   # Fear & Greed + VIX (legacy + SPY specialist)
│   ├── news_fetcher.py       # Titulares via NewsAPI
│   ├── macro/                # Dimensión 1 — FRED API
│   │   └── fred_client.py    # CPI, PCE, NFP, yield curve
│   ├── technical/            # Dimensión 2 — Multi-timeframe
│   │   └── multi_tf.py       # RSI, MACD, BB, SMA200 en 1D/4H/1H
│   ├── components/           # Dimensión 3 — Holdings y sectores
│   │   └── spy_holdings.py   # Top-10 + 11 sectores SPDR
│   ├── sentiment/            # Dimensión 4 — Sentimiento avanzado
│   │   ├── vix_term_structure.py  # Contango/backwardation VIX
│   │   └── put_call.py            # Put/Call ratio CBOE
│   ├── events/               # Dimensión 5 — Calendario
│   │   └── event_calendar.py # FOMC + economic calendar + geopolítica
│   └── cross_asset/          # Dimensión 6 — Cross-assets
│       └── cross_asset.py    # DXY, TLT, HYG, QQQ, GLD, USO, BTC
│
├── analysis/                 # Capa de análisis
│   ├── sentiment_analyzer.py # VADER NLP sobre titulares
│   ├── opportunity_scorer.py # Score compuesto legacy
│   ├── decision_engine.py    # Motor de decisión legacy (non-SPY)
│   ├── exit_evaluator.py     # 4 triggers de cierre forzado
│   ├── filters.py            # Pipeline de filtros en cascada SPY
│   ├── spy_cycle.py          # Orchestrador SPY — 6 dimensiones
│   └── claude_analyst.py     # Validación Claude AI con prompt caching
│
├── sender/                   # Capa de envío
│   ├── signal_formatter.py   # Construye payload para bot1 (buy + close + no_signal)
│   ├── webhook_client.py     # POST con reintentos + pending
│   └── telegram_notifier.py  # Alertas opcionales por Telegram
│
├── state/                    # Persistencia local
│   ├── last_signals.json     # Cooldown por símbolo
│   ├── open_positions.json   # Posición SPY abierta
│   ├── pending_signals.json  # Señales fallidas a reintentar
│   └── decision_log.jsonl   # Historial de decisiones (append-only)
│
├── logs/                     # Reportes de ciclo y registro histórico
│   ├── YYYY-MM-DD_HH-MM-SS.json   # Reporte completo por ciclo
│   └── trade_log.xlsx             # Registro Excel acumulativo (todas las operaciones)
│
└── docs/                     # Documentación completa
```

---

## Quick Start

```bash
# 1. Clonar y crear entorno virtual
git clone https://github.com/skeny65/Trading-agente-01.git
cd Trading-agente-01
python -m venv venv
.\venv\Scripts\activate      # Windows
source venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar credenciales
copy .env.example .env       # Windows
# Editar .env con las claves requeridas (ver environment_variables.md)

# 4. Probar análisis sin esperar horario de mercado
python run_analysis.py

# 5. Ejecutar en modo DRY_RUN (ciclo automático, sin enviar señales reales)
python agente01.py

# 6. Arranque rapido en Windows (tras reinicio)
start_agente01.bat
```

---

## Documentación Completa

| Documento | Contenido |
|-----------|-----------|
| [strategy.md](strategy.md) | **Estrategia SPY Specialist — 6 dimensiones, filtros en cascada, trailing dinámico** |
| [data_sources.md](data_sources.md) | Fuentes de datos en detalle — 12+ fuentes y cómo alimentan cada dimensión |
| [flow_summary.md](flow_summary.md) | Flujo completo del ciclo SPY de principio a fin |
| [architecture.md](architecture.md) | Diagrama de componentes e interacciones |
| [end_to_end_flow.md](end_to_end_flow.md) | Flujos completos con datos reales de ejemplo |
| [modules.md](modules.md) | Referencia de cada módulo y sus funciones |
| [data_schemas.md](data_schemas.md) | Estructura de todos los JSON y el Excel — payload, state, logs |
| [environment_variables.md](environment_variables.md) | Todas las variables de entorno explicadas |
| [deployment.md](deployment.md) | Guía de instalación y despliegue (Windows + Linux) |
