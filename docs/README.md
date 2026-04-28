# agente01 — Agente de Investigación Financiera Autónomo

## Visión General

agente01 es un agente autónomo cuyo **único objetivo es investigar y decidir**. Consulta múltiples fuentes financieras en internet, evalúa oportunidades mediante un sistema de scoring multifactorial, y envía una señal estructurada a **bot1** (Trading-bot) vía webhook HTTP para que este ejecute la orden en Alpaca.

El agente no ejecuta órdenes directamente. Todo su trabajo es investigación y análisis — al final de cada ciclo produce un único resultado: `APPROVE` o `NO_SIGNAL`.

```
agente01 (investigación + decisión)
    │
    └──► POST http://127.0.0.1:8000/webhook/bot2 ──► bot1 (Trading-bot) ──► Alpaca
```

Ambos bots corren en la misma PC y se comunican directamente por `127.0.0.1`.

---

## Fuentes de Información

El agente se alimenta de 5 fuentes para tomar cada decisión:

| # | Fuente | Dato obtenido | Peso en la decisión |
|---|--------|--------------|---------------------|
| 1 | **Yahoo Finance** (precio) | Precio, SMA20, SMA50, volumen, tendencia | 40% |
| 2 | **NewsAPI.org** | Titulares de las últimas 4h | — |
| 3 | **VADER NLP** (local) | Sentimiento de los titulares | 20% |
| 4 | **CNN Fear & Greed** | Sentimiento macro del mercado (0–100) | 25% |
| 5 | **Yahoo Finance** (^VIX) | Volatilidad implícita del mercado | 15% |

Para el detalle completo de cada fuente → ver [data_sources.md](data_sources.md).

---

## Arquitectura de Alto Nivel

```
┌────────────────────────────────────────────────────────────┐
│                        agente01                            │
│                                                            │
│  FUENTES          ANÁLISIS           DECISIÓN              │
│  ┌──────────┐    ┌──────────┐    ┌──────────────────┐      │
│  │Yahoo     │───►│Sentiment │───►│  Score 0.0–1.0   │      │
│  │Finance   │    │(VADER)   │    │  + Consenso 3/3  │      │
│  │NewsAPI   │    │Scorer    │    │  → APPROVE /      │      │
│  │CNN Fear  │    │Decision  │    │    NO_SIGNAL      │      │
│  │^VIX      │    │Engine    │    └────────┬─────────┘      │
│  └──────────┘    └──────────┘             │                │
│                                           ▼                │
│                     ┌──────────────────────────────┐       │
│  Exit Evaluator ───►│  Webhook Sender               │       │
│  (4 triggers de     │  127.0.0.1:8000               │       │
│   cierre forzado)   └──────────────────────────────┘       │
└────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP POST /webhook/bot2
┌────────────────────────────────────────────────────────────┐
│                    bot1 (Trading-bot)                      │
│              FastAPI en 127.0.0.1:8000                     │
│   Valida secret → Parsea señal → Ejecuta en Alpaca         │
└────────────────────────────────────────────────────────────┘
```

---

## Estrategia: Swing Trading con Trailing Stop Dinámico

agente01 opera bajo una estrategia de **swing trading** — posiciones de varios días que capturan movimientos de momentum sostenido. El trailing stop se calibra automáticamente según el régimen de volatilidad (VIX) en el momento de apertura.

| Parámetro | Valor |
|---|---|
| Ciclo de investigación | Cada **60 minutos** (horario de mercado) |
| Umbral de score | **0.70** |
| Consenso requerido | **3/3 señales** alineadas (trend + sentiment + macro) |
| Cooldown por símbolo | **24 horas** |
| Trailing stop | **3% / 4% / 5.5%** según régimen VIX |
| Take profit | Solo en VIX high (8%); en low/moderate se deja correr |
| Bloqueo VIX extremo | No se abren posiciones si VIX > 30 |
| Posiciones simultáneas | Máximo 12, exposición total <= 80% |

Para el detalle completo → ver [strategy.md](strategy.md).

## Características Principales

- **Investigación autónoma**: 5 fuentes de datos por ciclo — precios (SMA20+SMA50), noticias, sentimiento NLP, Fear & Greed, VIX.
- **Scoring recalibrado**: trend 40% + sentiment 20% + macro 25% + vix 15%.
- **Consenso 3/3**: Las 3 señales (tendencia, sentimiento, macro) deben apuntar a bullish para APPROVE.
- **Trailing dinámico por VIX**: 3% (VIX bajo) / 4% (moderado) / 5.5% (alto). Sin TP fijo en VIX bajo/moderado.
- **Invalidación de tesis**: 4 triggers de cierre forzado — VIX extremo, reversión con volumen, crash de sentimiento, tiempo máximo.
- **Seguimiento de posiciones**: `open_positions.json` evita dobles entradas y habilita los checks de salida.
- **Ciclos prioritarios**: 09:45, 12:30, 15:30 ET marcados con `[PRIORITY]` en logs.
- **Resiliencia ante fallos**: Señales no entregadas en `pending_signals.json`, reintentadas al próximo ciclo.
- **Log Excel completo**: Cada análisis (APPROVE, NO_SIGNAL, HOLDING, COOLDOWN, EXIT) queda registrado en `logs/trade_log.xlsx`.
- **Modo DRY_RUN**: Ciclo completo sin enviar señales reales a bot1.

---

## Estructura del Proyecto

```
Trading-agente-01/
├── agente01.py               # Entry point + APScheduler
├── run_analysis.py           # Ejecución manual fuera de horario (testing)
├── excel_logger.py           # Escritura de trade_log.xlsx (una fila por simbolo/ciclo)
├── config.py                 # Configuración central (carga .env)
├── .env                      # Credenciales (nunca commitear)
├── .env.example              # Plantilla de variables
├── requirements.txt          # Dependencias Python
├── start_agente01.bat        # Arranque rapido en Windows (doble click)
│
├── research/                 # Capa de investigación
│   ├── market_data.py        # Precio, volumen, SMA20, SMA50 via yfinance
│   ├── macro_indicators.py   # Fear & Greed + VIX
│   └── news_fetcher.py       # Titulares via NewsAPI
│
├── analysis/                 # Capa de análisis
│   ├── sentiment_analyzer.py # VADER NLP sobre titulares
│   ├── opportunity_scorer.py # Score compuesto 0.0–1.0
│   ├── decision_engine.py    # APPROVE / NO_SIGNAL + tamaño
│   └── exit_evaluator.py     # 4 triggers de cierre forzado de posiciones
│
├── sender/                   # Capa de envío
│   ├── signal_formatter.py   # Construye payload para bot1 (buy + close + no_signal)
│   ├── webhook_client.py     # POST con reintentos + pending
│   └── telegram_notifier.py  # Alertas opcionales por Telegram
│
├── state/                    # Persistencia local
│   ├── last_signals.json     # Cooldown por símbolo
│   ├── open_positions.json   # Posiciones abiertas activas
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
# Editar .env con NEWSAPI_KEY y WEBHOOK_SECRET (mismo que bot1)

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
| [strategy.md](strategy.md) | **Estrategia swing + trailing dinámico — parámetros, lógica, invalidación de tesis** |
| [data_sources.md](data_sources.md) | Fuentes de datos en detalle — cómo cada fuente alimenta la decisión |
| [flow_summary.md](flow_summary.md) | Flujo completo del ciclo de principio a fin |
| [architecture.md](architecture.md) | Diagrama de componentes e interacciones |
| [end_to_end_flow.md](end_to_end_flow.md) | Los flujos completos con datos reales de ejemplo |
| [modules.md](modules.md) | Referencia de cada módulo y sus funciones |
| [data_schemas.md](data_schemas.md) | Estructura de todos los JSON y el Excel — payload, state, logs |
| [environment_variables.md](environment_variables.md) | Todas las variables de entorno explicadas |
| [deployment.md](deployment.md) | Guía de instalación y despliegue (Windows + Linux) |
