# Variables de Entorno — agente01 (SPY Specialist)

Todas las variables se configuran en el archivo `.env` en la raíz del proyecto. Nunca commitear este archivo (está en `.gitignore`).

Usa `.env.example` como plantilla.

---

## Variables Obligatorias

### ANTHROPIC_API_KEY
- **Descripción**: Clave de autenticación para la API de Claude (Anthropic)
- **Dónde obtenerla**: https://console.anthropic.com → API Keys
- **Ejemplo**: `ANTHROPIC_API_KEY=sk-ant-api03-...`
- **Efecto si falta**: `config.validate()` aborta el arranque con error. Claude AI no puede validar las señales.

### WEBHOOK_SECRET
- **Descripción**: Secreto compartido entre agente01 y bot1 para autenticar webhooks
- **Debe coincidir con**: el valor de `WEBHOOK_SECRET` en el `.env` de bot1 (Trading-bot)
- **Ejemplo**: `WEBHOOK_SECRET=a_secure_random_string_32chars_min`
- **Efecto si falta**: `config.validate()` aborta el arranque con error
- **Efecto si es incorrecto**: bot1 rechaza con HTTP 401

---

## Variables Recomendadas (con fallbacks funcionales si faltan)

### TWELVE_DATA_API_KEY
- **Descripción**: Clave para Twelve Data — fuente de precios OHLCV complementaria a Yahoo Finance
- **Dónde obtenerla**: https://twelvedata.com → Sign Up → Free Plan
- **Ejemplo**: `TWELVE_DATA_API_KEY=132896822e8d48dfac66cae7c0858711`
- **Efecto si falta**: Los módulos de precios solo usan Yahoo Finance. Twelve Data queda desactivado.
- **Nota**: El free tier incluye 800 llamadas/día. El agente tiene un contador interno que se resetea cada día calendario.

### TWELVE_DATA_DAILY_LIMIT
- **Descripción**: Límite diario de llamadas a Twelve Data (buffer de seguridad bajo el límite real de 800)
- **Default**: `790`
- **Cuándo cambiar**: Si upgrade a plan pago, aumentar según el plan
- **Ejemplo**: `TWELVE_DATA_DAILY_LIMIT=790`

### FRED_API_KEY
- **Descripción**: Clave para la API de datos macro de la Federal Reserve (FRED)
- **Dónde obtenerla**: https://fred.stlouisfed.org/docs/api/api_key.html (gratuita)
- **Ejemplo**: `FRED_API_KEY=abcdef1234567890abcdef1234567890`
- **Efecto si falta**: La dimensión Macro usa score neutral (0.5). El agente sigue funcionando pero sin datos macro reales (CPI, PCE, NFP, yield curve).

### NEWSAPI_KEY
- **Descripción**: Clave para NewsAPI.org — titulares para el VADER sentiment
- **Dónde obtenerla**: https://newsapi.org (plan gratuito: 100 requests/día)
- **Ejemplo**: `NEWSAPI_KEY=d3bb2947e2c74b7692718602121a0083`
- **Efecto si falta**: Sin titulares → VADER score es neutral (0.5). El componente VADER de sentimiento queda en fallback.

---

## Variables con Valores por Defecto

### WEBHOOK_URL
- **Descripción**: URL donde bot1 está escuchando webhooks de bot2
- **Default**: `http://127.0.0.1:8000/webhook/bot2`
- **Cuándo cambiar**: Si bot1 corre en otra máquina, usar la URL pública de ngrok
- **Ejemplo**: `WEBHOOK_URL=http://127.0.0.1:8000/webhook/bot2`

### SYMBOL
- **Descripción**: Símbolo del SPY Specialist (no modificar)
- **Default**: `SPY`
- **Nota**: El sistema está diseñado exclusivamente para SPY
- **Ejemplo**: `SYMBOL=SPY`

### CYCLE_INTERVAL_MINUTES
- **Descripción**: Cada cuántos minutos se repite el ciclo de investigación
- **Default**: `60`
- **Nota**: El agente analiza solo en horario de mercado.
- **Ejemplo**: `CYCLE_INTERVAL_MINUTES=60`

### MIN_CONFIDENCE
- **Descripción**: Score mínimo (ajustado por multiplicador de eventos) para pasar el gate de aprobación
- **Default**: `0.72`
- **Rango**: 0.0–1.0 (más alto = más restrictivo = menos señales)
- **Nota**: El gate también exige MIN_DIMENSIONS_PASSING dimensiones > 0.55
- **Ejemplo**: `MIN_CONFIDENCE=0.72`

### MIN_DIMENSIONS_PASSING
- **Descripción**: Número mínimo de dimensiones con score > 0.55 para APPROVE
- **Default**: `5`
- **Rango**: 1–6 (5 de 6 es el estándar del SPY Specialist)
- **Ejemplo**: `MIN_DIMENSIONS_PASSING=5`

### COOLDOWN_HOURS
- **Descripción**: Ventana de tiempo después de enviar una señal en la que no se repite
- **Default**: `24`
- **Nota**: Para SPY, el cooldown efectivo es "mientras haya posición abierta" (open_positions.json)
- **Ejemplo**: `COOLDOWN_HOURS=24`

### NEWS_LOOKBACK_HOURS
- **Descripción**: Ventana de tiempo hacia atrás para buscar noticias en NewsAPI
- **Default**: `4`
- **Ejemplo**: `NEWS_LOOKBACK_HOURS=4`

### PRICE_HISTORY_DAYS
- **Descripción**: Días de historial de precios a descargar de Yahoo Finance
- **Default**: `60`
- **Por qué 60**: Necesario para calcular SMA50 con datos suficientes
- **Ejemplo**: `PRICE_HISTORY_DAYS=60`

---

## Variables de Claude AI

### CLAUDE_MODEL
- **Descripción**: Modelo Claude usado como motor de decisión final
- **Default**: `claude-haiku-4-5-20251001`
- **Alternativas**: `claude-sonnet-4-6` (mayor capacidad, mayor costo)
- **Nota**: El prompt del sistema usa `cache_control: ephemeral` para reducir costo por ciclo
- **Ejemplo**: `CLAUDE_MODEL=claude-haiku-4-5-20251001`

### CLAUDE_MAX_TOKENS
- **Descripción**: Máximo de tokens en la respuesta de Claude
- **Default**: `512`
- **Nota**: Claude solo devuelve un JSON compacto — 512 es suficiente
- **Ejemplo**: `CLAUDE_MAX_TOKENS=512`

---

## Variables de Trailing Stop Dinámico

### EXIT_STRATEGY
- **Default**: `trailing_stop`
- **Nota**: Solo se soporta trailing_stop actualmente
- **Ejemplo**: `EXIT_STRATEGY=trailing_stop`

### TRAIL_PERCENT_LOW_VIX
- **Descripción**: Trailing stop para régimen VIX bajo (VIX < 15)
- **Default**: `3.0` (3%)
- **Ejemplo**: `TRAIL_PERCENT_LOW_VIX=3.0`

### TRAIL_PERCENT_MODERATE_VIX
- **Descripción**: Trailing stop para régimen VIX moderado (VIX 15–25)
- **Default**: `4.0` (4%)
- **Ejemplo**: `TRAIL_PERCENT_MODERATE_VIX=4.0`

### TRAIL_PERCENT_HIGH_VIX
- **Descripción**: Trailing stop para régimen VIX alto (VIX 25–30)
- **Default**: `5.5` (5.5%)
- **Ejemplo**: `TRAIL_PERCENT_HIGH_VIX=5.5`

### TAKE_PROFIT_HIGH_VIX
- **Descripción**: Take profit fijo (%) para régimen VIX alto
- **Default**: `8.0` (8%)
- **Aplica**: Solo cuando `vix_regime == "high"`. En low/moderate se deja correr sin TP.
- **Ejemplo**: `TAKE_PROFIT_HIGH_VIX=8.0`

### MAX_HOLDING_DAYS_LOW
- **Default**: `15`
- **Ejemplo**: `MAX_HOLDING_DAYS_LOW=15`

### MAX_HOLDING_DAYS_MODERATE
- **Default**: `10`
- **Ejemplo**: `MAX_HOLDING_DAYS_MODERATE=10`

### MAX_HOLDING_DAYS_HIGH
- **Default**: `7`
- **Ejemplo**: `MAX_HOLDING_DAYS_HIGH=7`

---

## Variables de Position Sizing — 4 Tiers

### SIZE_TIER_1
- **Descripción**: Tamaño de posición cuando score >= 0.90
- **Default**: `0.25` (25% del capital)
- **Ejemplo**: `SIZE_TIER_1=0.25`

### SIZE_TIER_2
- **Descripción**: Tamaño de posición cuando score >= 0.82
- **Default**: `0.18` (18% del capital)
- **Ejemplo**: `SIZE_TIER_2=0.18`

### SIZE_TIER_3
- **Descripción**: Tamaño de posición cuando score >= 0.75
- **Default**: `0.12` (12% del capital)
- **Ejemplo**: `SIZE_TIER_3=0.12`

### SIZE_TIER_4
- **Descripción**: Tamaño de posición cuando score >= 0.72 (mínimo para APPROVE)
- **Default**: `0.08` (8% del capital)
- **Ejemplo**: `SIZE_TIER_4=0.08`

---

## Modo de Operación

### DRY_RUN
- **Descripción**: Modo de simulación. Si `true`, todo el ciclo corre normalmente pero el webhook NO se envía a bot1
- **Default**: `true`
- **Valores**: `true` | `false`
- **Nota**: En DRY_RUN=true, los logs JSON y el Excel se escriben normalmente — solo se omite el POST real a bot1. El `webhook_status` en Excel queda como `"dry_run"`.
- **Recomendación**: Empezar siempre en `true`, cambiar a `false` solo cuando el ciclo esté verificado
- **Ejemplo**: `DRY_RUN=true`

---

## Variables Opcionales

### TELEGRAM_BOT_TOKEN
- **Descripción**: Token del bot de Telegram para enviar alertas
- **Cómo obtener**: Hablar con @BotFather en Telegram → `/newbot`
- **Efecto si vacío**: Las alertas se omiten silenciosamente (el agente sigue funcionando)
- **Ejemplo**: `TELEGRAM_BOT_TOKEN=1234567890:AAHdqTcvCH1vGWJxfSeofSh0riMLapfDGE`

### TELEGRAM_CHAT_ID
- **Descripción**: ID del chat donde se envían las alertas (usuario o grupo)
- **Cómo obtener**: Enviar un mensaje al bot y consultar `https://api.telegram.org/bot<TOKEN>/getUpdates`
- **Ejemplo**: `TELEGRAM_CHAT_ID=123456789`

---

## .env completo de referencia

```bash
# ── Claude AI (requerido para el motor de decisión) ───────────
ANTHROPIC_API_KEY=sk-ant-api03-tu_clave_aqui

# ── Twelve Data (fuente de precios complementaria — free tier) ─
TWELVE_DATA_API_KEY=tu_api_key_de_twelvedata
TWELVE_DATA_DAILY_LIMIT=790

# ── FRED API (recomendado — dimensión Macro) ──────────────────
FRED_API_KEY=tu_clave_fred

# ── NewsAPI (opcional — VADER sentiment) ─────────────────────
NEWSAPI_KEY=tu_api_key_de_newsapi

# ── Webhook (bot1) — requerido ────────────────────────────────
WEBHOOK_SECRET=mismo_secreto_que_bot1_minimo_32_chars
WEBHOOK_URL=http://127.0.0.1:8000/webhook/bot2

# ── Símbolo (no modificar) ────────────────────────────────────
SYMBOL=SPY

# ── Ciclo (en minutos) ────────────────────────────────────────
CYCLE_INTERVAL_MINUTES=60

# ── Umbrales de decision ──────────────────────────────────────
MIN_CONFIDENCE=0.72
MIN_DIMENSIONS_PASSING=5
COOLDOWN_HOURS=24

# ── Ventanas de datos ─────────────────────────────────────────
NEWS_LOOKBACK_HOURS=4
PRICE_HISTORY_DAYS=60

# ── Claude AI ─────────────────────────────────────────────────
CLAUDE_MODEL=claude-haiku-4-5-20251001
CLAUDE_MAX_TOKENS=512

# ── Trailing stop dinamico por regimen VIX ────────────────────
EXIT_STRATEGY=trailing_stop
TRAIL_PERCENT_LOW_VIX=3.0
TRAIL_PERCENT_MODERATE_VIX=4.0
TRAIL_PERCENT_HIGH_VIX=5.5
TAKE_PROFIT_HIGH_VIX=8.0

MAX_HOLDING_DAYS_LOW=15
MAX_HOLDING_DAYS_MODERATE=10
MAX_HOLDING_DAYS_HIGH=7

# ── Position sizing — 4 tiers ────────────────────────────────
SIZE_TIER_1=0.25
SIZE_TIER_2=0.18
SIZE_TIER_3=0.12
SIZE_TIER_4=0.08

# ── Modo de operacion ─────────────────────────────────────────
# true  -> solo loguea, NO envia webhook real a bot1
# false -> envia webhook real
DRY_RUN=true

# ── Telegram (opcional) ───────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## Buenas Prácticas de Seguridad

- Agregar `.env` a `.gitignore` (ya configurado en este proyecto)
- Usar secretos de al menos 32 caracteres para `WEBHOOK_SECRET`
- Rotar `ANTHROPIC_API_KEY` y `FRED_API_KEY` si se exponen accidentalmente
- No loguear el valor de `WEBHOOK_SECRET` ni `ANTHROPIC_API_KEY` en ningún módulo
- `ANTHROPIC_API_KEY` tiene costo por uso — monitorear en console.anthropic.com
