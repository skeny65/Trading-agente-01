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
| 1 | **Yahoo Finance** (precio) | Precio, SMA20, volumen, tendencia | 30% |
| 2 | **NewsAPI.org** | Titulares de las últimas 6h | — |
| 3 | **VADER NLP** (local) | Sentimiento de los titulares | 30% |
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
│  │Finance   │    │(VADER)   │    │  + Consenso 2/3  │      │
│  │NewsAPI   │    │Scorer    │    │  → APPROVE /      │      │
│  │CNN Fear  │    │Decision  │    │    NO_SIGNAL      │      │
│  │^VIX      │    │Engine    │    └────────┬─────────┘      │
│  └──────────┘    └──────────┘             │                │
│                                           ▼                │
│                               ┌───────────────────┐        │
│                               │  Webhook Sender   │        │
│                               │  127.0.0.1:8000   │        │
│                               └───────────────────┘        │
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

## Características Principales

- **Investigación autónoma**: 5 fuentes de datos por ciclo — precios, noticias, sentimiento NLP, Fear & Greed, VIX.
- **Scoring multifactorial**: Score compuesto 0.0–1.0 con 4 componentes ponderados.
- **Motor de decisión con consenso**: Requiere al menos 2 de 3 señales alineadas (tendencia + sentimiento + macro) para APPROVE.
- **Tamaño dinámico de posición**: 5% / 10% / 15% según la confianza.
- **Cooldown por símbolo**: Evita señales duplicadas dentro de la ventana configurada.
- **Resiliencia ante fallos**: Señales no entregadas se guardan en `pending_signals.json` y se reenvían al próximo ciclo.
- **Manejo de rechazo**: Respeta la decisión del manager de bot1 sin reintentar.
- **No-signal informativo**: Envía a bot1 un payload `no_signal` con el motivo cuando ningún símbolo supera el umbral.
- **Alertas Telegram**: Notifica en tiempo real cada decisión relevante.
- **Ciclo de reportes**: Cada ejecución genera un JSON completo en `logs/` con todo el análisis.
- **Modo DRY_RUN**: Simula todo el ciclo sin enviar señales reales a bot1.

---

## Estructura del Proyecto

```
Trading-agente-01/
├── agente01.py               # Entry point + APScheduler
├── run_analysis.py           # Ejecución manual fuera de horario (testing)
├── config.py                 # Configuración central (carga .env)
├── .env                      # Credenciales (nunca commitear)
├── .env.example              # Plantilla de variables
├── requirements.txt          # Dependencias Python
│
├── research/                 # Capa de investigación
│   ├── market_data.py        # Precio, volumen, SMA20 via yfinance
│   ├── macro_indicators.py   # Fear & Greed + VIX
│   └── news_fetcher.py       # Titulares via NewsAPI
│
├── analysis/                 # Capa de análisis
│   ├── sentiment_analyzer.py # VADER NLP sobre titulares
│   ├── opportunity_scorer.py # Score compuesto 0.0–1.0
│   └── decision_engine.py    # APPROVE / NO_SIGNAL + tamaño
│
├── sender/                   # Capa de envío
│   ├── signal_formatter.py   # Construye payload para bot1
│   ├── webhook_client.py     # POST con reintentos + pending
│   └── telegram_notifier.py  # Alertas opcionales por Telegram
│
├── state/                    # Persistencia local
│   ├── last_signals.json     # Cooldown por símbolo
│   ├── pending_signals.json  # Señales fallidas a reintentar
│   └── decision_log.jsonl    # Historial de decisiones
│
├── logs/                     # Reportes JSON de cada ciclo
│   └── YYYY-MM-DD_HH-MM-SS.json
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
```

---

## Documentación Completa

| Documento | Contenido |
|-----------|-----------|
| [data_sources.md](data_sources.md) | **Fuentes de datos en detalle — cómo cada fuente alimenta la decisión** |
| [flow_summary.md](flow_summary.md) | Flujo completo del ciclo de principio a fin |
| [architecture.md](architecture.md) | Diagrama de componentes e interacciones |
| [end_to_end_flow.md](end_to_end_flow.md) | Los 4 flujos completos con datos reales de ejemplo |
| [modules.md](modules.md) | Referencia de cada módulo y sus funciones |
| [data_schemas.md](data_schemas.md) | Estructura de todos los JSON — payload, state, logs |
| [environment_variables.md](environment_variables.md) | Todas las variables de entorno explicadas |
| [deployment.md](deployment.md) | Guía de instalación y despliegue (Windows + Linux) |
