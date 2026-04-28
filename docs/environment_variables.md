# Variables de Entorno — agente01

Todas las variables se configuran en el archivo `.env` en la raíz del proyecto. Nunca commitear este archivo (está en `.gitignore`).

Usa `.env.example` como plantilla.

---

## Variables Obligatorias

### NEWSAPI_KEY
- **Descripción**: Clave de autenticación para NewsAPI.org
- **Dónde obtenerla**: https://newsapi.org (plan gratuito: 100 requests/día)
- **Ejemplo**: `NEWSAPI_KEY=d3bb2947e2c74b7692718602121a0083`
- **Efecto si falta**: `config.validate()` aborta el arranque con error

### WEBHOOK_SECRET
- **Descripción**: Secreto compartido entre agente01 y bot1 para autenticar webhooks
- **Debe coincidir con**: el valor de `WEBHOOK_SECRET` en el `.env` de bot1 (Trading-bot)
- **Ejemplo**: `WEBHOOK_SECRET=a_secure_random_string`
- **Efecto si falta**: `config.validate()` aborta el arranque con error
- **Efecto si es incorrecto**: bot1 rechaza con HTTP 401

---

## Variables con Valores por Defecto

### WEBHOOK_URL
- **Descripción**: URL donde bot1 está escuchando webhooks de bot2
- **Default**: `http://127.0.0.1:8000/webhook/bot2`
- **Cuándo cambiar**: Si bot1 corre en otra máquina, usar la URL pública de ngrok
- **Ejemplo**: `WEBHOOK_URL=http://127.0.0.1:8000/webhook/bot2`

### WATCHLIST
- **Descripción**: Símbolos que agente01 monitorea en cada ciclo, separados por coma
- **Default**: `SPY,QQQ,IWM,DIA,XLK,XLF,XLE,XLV`
- **Símbolos soportados**: Cualquier ticker válido de Yahoo Finance (acciones, ETFs)
- **Recomendación**: ETFs de índice de alta liquidez para swing trading
- **Ejemplo**: `WATCHLIST=SPY,QQQ,IWM,DIA,XLK,XLF,XLE,XLV`

### CYCLE_INTERVAL_MINUTES
- **Descripción**: Cada cuántos minutos se repite el ciclo de investigación
- **Default**: `60`
- **Nota**: El agente analiza solo en horario de mercado. Fuera del horario, el ciclo se omite pero el scheduler sigue corriendo.
- **Ejemplo**: `CYCLE_INTERVAL_MINUTES=60`

### MIN_CONFIDENCE
- **Descripción**: Score mínimo que debe alcanzar un símbolo para pasar a la regla de consenso
- **Default**: `0.70`
- **Rango**: 0.0–1.0 (más alto = más restrictivo = menos señales)
- **Recomendado**: 0.70–0.80 para swing trading de calidad
- **Ejemplo**: `MIN_CONFIDENCE=0.70`

### CONSENSUS_REQUIRED
- **Descripción**: Número de señales cualitativas bullish requeridas (de 3 posibles)
- **Default**: `3`
- **Nota**: Para swing trading se requiere 3/3 — tendencia, sentimiento y macro deben ser bullish simultáneamente
- **Ejemplo**: `CONSENSUS_REQUIRED=3`

### COOLDOWN_HOURS
- **Descripción**: Ventana de tiempo después de enviar una señal en la que no se repite el mismo símbolo
- **Default**: `24`
- **Propósito**: Un swing dura días — no se reabre una posición en horas
- **Ejemplo**: `COOLDOWN_HOURS=24`

### NEWS_LOOKBACK_HOURS
- **Descripción**: Ventana de tiempo hacia atrás para buscar noticias en NewsAPI
- **Default**: `4`
- **Relación con el ciclo**: 4h de noticias con ciclo de 1h → buena cobertura sin noticias obsoletas
- **Ejemplo**: `NEWS_LOOKBACK_HOURS=4`

### PRICE_HISTORY_DAYS
- **Descripción**: Días de historial de precios a descargar de Yahoo Finance
- **Default**: `60`
- **Por qué 60**: Necesario para calcular SMA50 con datos suficientes (mínimo 50 días)
- **Ejemplo**: `PRICE_HISTORY_DAYS=60`

---

## Variables de Trailing Stop Dinámico

### EXIT_STRATEGY
- **Descripción**: Estrategia de salida enviada a bot1
- **Default**: `trailing_stop`
- **Nota**: Actualmente solo se soporta `trailing_stop`
- **Ejemplo**: `EXIT_STRATEGY=trailing_stop`

### TRAIL_PERCENT_LOW_VIX
- **Descripción**: Trailing stop para régimen VIX bajo (VIX < 15)
- **Default**: `3.0` (3%)
- **Justificación**: Mercado calmado — trailing ajustado para maximizar ganancias
- **Ejemplo**: `TRAIL_PERCENT_LOW_VIX=3.0`

### TRAIL_PERCENT_MODERATE_VIX
- **Descripción**: Trailing stop para régimen VIX moderado (VIX 15–20)
- **Default**: `4.0` (4%)
- **Ejemplo**: `TRAIL_PERCENT_MODERATE_VIX=4.0`

### TRAIL_PERCENT_HIGH_VIX
- **Descripción**: Trailing stop para régimen VIX alto (VIX 20–30)
- **Default**: `5.5` (5.5%)
- **Justificación**: Alta volatilidad — el trade necesita más espacio para respirar
- **Ejemplo**: `TRAIL_PERCENT_HIGH_VIX=5.5`

### TAKE_PROFIT_HIGH_VIX
- **Descripción**: Take profit fijo (%) para régimen VIX alto
- **Default**: `8.0` (8%)
- **Aplica**: Solo cuando `vix_regime == "high"`. En low/moderate se deja correr sin TP.
- **Ejemplo**: `TAKE_PROFIT_HIGH_VIX=8.0`

### BLOCK_NEW_ON_EXTREME_VIX
- **Descripción**: Si `true`, bloquea la apertura de nuevas posiciones cuando VIX > 30
- **Default**: `true`
- **Ejemplo**: `BLOCK_NEW_ON_EXTREME_VIX=true`

### MAX_HOLDING_DAYS_LOW
- **Descripción**: Días máximos de holding para régimen VIX bajo
- **Default**: `15`
- **Ejemplo**: `MAX_HOLDING_DAYS_LOW=15`

### MAX_HOLDING_DAYS_MODERATE
- **Descripción**: Días máximos de holding para régimen VIX moderado
- **Default**: `10`
- **Ejemplo**: `MAX_HOLDING_DAYS_MODERATE=10`

### MAX_HOLDING_DAYS_HIGH
- **Descripción**: Días máximos de holding para régimen VIX alto
- **Default**: `7`
- **Ejemplo**: `MAX_HOLDING_DAYS_HIGH=7`

---

## Variables de Position Sizing

### SIZE_HIGH_CONFIDENCE
- **Descripción**: Tamaño de posición cuando score >= 0.85
- **Default**: `0.08` (8% del capital)
- **Ejemplo**: `SIZE_HIGH_CONFIDENCE=0.08`

### SIZE_MEDIUM_CONFIDENCE
- **Descripción**: Tamaño de posición cuando score >= 0.78
- **Default**: `0.05` (5% del capital)
- **Ejemplo**: `SIZE_MEDIUM_CONFIDENCE=0.05`

### SIZE_LOW_CONFIDENCE
- **Descripción**: Tamaño de posición cuando score >= 0.70 (mínimo para APPROVE)
- **Default**: `0.03` (3% del capital)
- **Ejemplo**: `SIZE_LOW_CONFIDENCE=0.03`

### MAX_CONCURRENT_POSITIONS
- **Descripción**: Número máximo de posiciones abiertas simultáneamente
- **Default**: `12`
- **Nota**: El agente usa `open_positions.json` para tracking, pero la limitación real la aplica bot1
- **Ejemplo**: `MAX_CONCURRENT_POSITIONS=12`

### MAX_TOTAL_EXPOSURE
- **Descripción**: Exposición máxima total como fracción del capital (0.0–1.0)
- **Default**: `0.80` (80%)
- **Ejemplo**: `MAX_TOTAL_EXPOSURE=0.80`

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
# ── NewsAPI ───────────────────────────────────────────────
NEWSAPI_KEY=tu_api_key_de_newsapi

# ── Webhook (bot1) ────────────────────────────────────────
WEBHOOK_SECRET=mismo_secreto_que_bot1
WEBHOOK_URL=http://127.0.0.1:8000/webhook/bot2

# ── Simbolos a monitorear ─────────────────────────────────
WATCHLIST=SPY,QQQ,IWM,DIA,XLK,XLF,XLE,XLV

# ── Ciclo (en minutos) ────────────────────────────────────
CYCLE_INTERVAL_MINUTES=60

# ── Umbrales de decision ──────────────────────────────────
MIN_CONFIDENCE=0.70
CONSENSUS_REQUIRED=3
COOLDOWN_HOURS=24

# ── Ventanas de datos ─────────────────────────────────────
NEWS_LOOKBACK_HOURS=4
PRICE_HISTORY_DAYS=60

# ── Trailing stop dinamico por regimen VIX ────────────────
EXIT_STRATEGY=trailing_stop
TRAIL_PERCENT_LOW_VIX=3.0
TRAIL_PERCENT_MODERATE_VIX=4.0
TRAIL_PERCENT_HIGH_VIX=5.5
TAKE_PROFIT_HIGH_VIX=8.0
BLOCK_NEW_ON_EXTREME_VIX=true

MAX_HOLDING_DAYS_LOW=15
MAX_HOLDING_DAYS_MODERATE=10
MAX_HOLDING_DAYS_HIGH=7

# ── Position sizing conservador ───────────────────────────
SIZE_HIGH_CONFIDENCE=0.08
SIZE_MEDIUM_CONFIDENCE=0.05
SIZE_LOW_CONFIDENCE=0.03
MAX_CONCURRENT_POSITIONS=12
MAX_TOTAL_EXPOSURE=0.80

# ── Modo de operacion ─────────────────────────────────────
# true  -> solo loguea, NO envia webhook real a bot1
# false -> envia webhook real
DRY_RUN=true

# ── Telegram (opcional) ───────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## Buenas Prácticas de Seguridad

- Agregar `.env` a `.gitignore` (ya configurado en este proyecto)
- Usar secretos de al menos 32 caracteres para `WEBHOOK_SECRET`
- Rotar `NEWSAPI_KEY` si se expone accidentalmente
- No loguear el valor de `WEBHOOK_SECRET` en ningún módulo
