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
- **Ejemplo**: `WEBHOOK_SECRET=mi_secreto_super_largo_de_32_caracteres`
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
- **Default**: `SPY,QQQ`
- **Símbolos soportados**: Cualquier ticker válido de Yahoo Finance (acciones, ETFs, crypto como `BTC-USD`, `ETH-USD`)
- **Ejemplo**: `WATCHLIST=SPY,QQQ,BTC-USD`

### CYCLE_INTERVAL_HOURS
- **Descripción**: Cada cuántas horas se repite el ciclo de investigación
- **Default**: `4`
- **Rango recomendado**: 2–6 horas (menos es más costoso en API calls de NewsAPI)
- **Ejemplo**: `CYCLE_INTERVAL_HOURS=4`

### MIN_CONFIDENCE
- **Descripción**: Score mínimo que debe alcanzar un símbolo para generar señal de compra
- **Default**: `0.65`
- **Rango**: 0.0–1.0 (más alto = más restrictivo = menos señales)
- **Recomendado**: 0.65–0.75 para equilibrio calidad/frecuencia
- **Ejemplo**: `MIN_CONFIDENCE=0.65`

### COOLDOWN_HOURS
- **Descripción**: Ventana de tiempo después de enviar una señal en la que no se repite el mismo símbolo
- **Default**: `4`
- **Propósito**: Evitar señales duplicadas en ciclos consecutivos
- **Ejemplo**: `COOLDOWN_HOURS=4`

### DEFAULT_STOP_LOSS
- **Descripción**: Stop loss por defecto incluido en el payload a bot1 (fracción del precio)
- **Default**: `0.02` (2%)
- **Nota**: agente01 envía este valor como referencia; bot1 decide si lo usa según su propia lógica
- **Ejemplo**: `DEFAULT_STOP_LOSS=0.02`

### DEFAULT_TAKE_PROFIT
- **Descripción**: Take profit por defecto incluido en el payload a bot1 (fracción del precio)
- **Default**: `0.04` (4%)
- **Ratio riesgo/beneficio**: 1:2 con el stop loss por defecto
- **Ejemplo**: `DEFAULT_TAKE_PROFIT=0.04`

### DRY_RUN
- **Descripción**: Modo de simulación. Si `true`, todo el ciclo corre normalmente pero el webhook no se envía a bot1
- **Default**: `true`
- **Valores**: `true` | `false`
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

## Resumen

```bash
# .env mínimo para arrancar
NEWSAPI_KEY=tu_api_key
WEBHOOK_SECRET=mismo_que_bot1

# .env completo recomendado
NEWSAPI_KEY=tu_api_key
WEBHOOK_SECRET=mismo_que_bot1
WEBHOOK_URL=http://127.0.0.1:8000/webhook/bot2
WATCHLIST=SPY,QQQ
CYCLE_INTERVAL_HOURS=4
MIN_CONFIDENCE=0.65
COOLDOWN_HOURS=4
DEFAULT_STOP_LOSS=0.02
DEFAULT_TAKE_PROFIT=0.04
DRY_RUN=true
TELEGRAM_BOT_TOKEN=         # opcional
TELEGRAM_CHAT_ID=           # opcional
```

## Buenas Prácticas de Seguridad

- Agregar `.env` a `.gitignore` (ya configurado en este proyecto)
- Usar secretos de al menos 32 caracteres para `WEBHOOK_SECRET`
- Rotar `NEWSAPI_KEY` si se expone accidentalmente
- No loguear el valor de `WEBHOOK_SECRET` en ningún módulo
