# Guía de Despliegue — agente01

## Requisitos Previos

- Python 3.11 o superior
- bot1 (Trading-bot) corriendo en `127.0.0.1:8000` con endpoint `/webhook/bot2`
- Cuenta gratuita en NewsAPI.org
- Windows 10/11 (instrucciones principales) o Linux/macOS

---

## Instalación en Windows

### 1. Clonar el repositorio

```bash
git clone https://github.com/skeny65/Trading-agente-01.git
cd Trading-agente-01
```

### 2. Crear entorno virtual

```bash
python -m venv venv
.\venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar credenciales

```bash
copy .env.example .env
```

Editar `.env` con los valores correctos (ver [environment_variables.md](environment_variables.md)).

**Mínimo requerido:**
```
NEWSAPI_KEY=tu_clave_de_newsapi
WEBHOOK_SECRET=mismo_secreto_que_bot1
```

### 5. Verificar que bot1 está corriendo

```bash
curl http://localhost:8000/health
# Debe responder: {"status": "healthy", ...}
```

### 6. Ejecutar en modo DRY_RUN (recomendado para primer arranque)

Asegúrate de que `.env` tiene `DRY_RUN=true`, luego:

```bash
python agente01.py
```

Deberías ver logs del ciclo completo sin que se envíe ningún webhook real.

---

## Configuración de Ambos Bots en Paralelo

Para correr agente01 y bot1 simultáneamente en Windows, puedes usar dos terminales o crear un script:

**Terminal 1 — bot1:**
```bash
cd C:\ruta\a\Trading-bot
.\venv\Scripts\activate
python bot.py
```

**Terminal 2 — agente01:**
```bash
cd C:\ruta\a\Trading-agente-01
.\venv\Scripts\activate
python agente01.py
```

Alternativamente, crear `start_agente01.bat`:
```batch
@echo off
cd /d C:\Users\kenyb\Desktop\GEMINI\Trading-agente-01
call venv\Scripts\activate
python agente01.py
pause
```

---

## Verificación Post-arranque

### Logs esperados al iniciar

```
2026-04-27 09:30:00 [INFO] agente01 — agente01 iniciado | modo=DRY RUN | watchlist=['SPY', 'QQQ']
2026-04-27 09:30:00 [INFO] agente01 — Ciclo cada 4h | umbral=0.65
2026-04-27 09:30:00 [INFO] agente01 — ============================================================
2026-04-27 09:30:00 [INFO] agente01 — INICIO DE CICLO
2026-04-27 09:30:01 [INFO] research.macro_indicators — Macro: Fear&Greed=62 (Greed) | VIX=15.3 (moderate) | bias=bullish
2026-04-27 09:30:02 [INFO] research.market_data — SPY: $512.30 (+1.20%) | trend=bullish | vol_ratio=1.40x
2026-04-27 09:30:03 [INFO] research.news_fetcher — SPY: 8 titulares en las últimas 6h
2026-04-27 09:30:03 [INFO] analysis.sentiment_analyzer — Sentiment: compound=0.340 (positive) | pos=62% neg=12% | n=8
2026-04-27 09:30:03 [INFO] analysis.opportunity_scorer — Score [SPY]: total=0.712 | sentiment=0.67 trend=1.00 macro=0.62 vix=0.65
2026-04-27 09:30:03 [INFO] analysis.decision_engine — APPROVE [SPY]: BUY | confidence=0.712 | size=0.05
2026-04-27 09:30:03 [INFO] sender.webhook_client — [DRY_RUN] Webhook NO enviado — BUY SPY
```

### Verificar archivos de estado

```bash
# Ver última señal por símbolo
cat state/last_signals.json

# Ver historial de decisiones (últimas 5)
# Windows PowerShell:
Get-Content state\decision_log.jsonl | Select-Object -Last 5

# Ver señales pendientes
cat state/pending_signals.json
```

---

## Pasar a Modo LIVE

Cuando hayas verificado que el ciclo funciona correctamente en DRY_RUN:

1. Editar `.env`:
   ```
   DRY_RUN=false
   ```

2. Verificar que el `WEBHOOK_SECRET` coincide exactamente con el de bot1

3. Verificar que bot1 está en modo paper trading (`ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2`)

4. Reiniciar agente01:
   ```bash
   python agente01.py
   ```

---

## Solución de Problemas

### Error: "Variables de entorno faltantes: NEWSAPI_KEY"
→ El archivo `.env` no existe o le falta la variable. Copiar `.env.example` a `.env` y rellenar.

### Error: "bot1 no disponible" en los logs
→ bot1 no está corriendo. Iniciar bot1 primero en otra terminal.

### HTTP 401 de bot1
→ `WEBHOOK_SECRET` en agente01 no coincide con el de bot1. Verificar ambos `.env`.

### Score siempre bajo (ciclos sin señales)
→ Normal en mercados laterales o con alta volatilidad. Revisar logs para ver qué componente puntúa bajo. Opcionalmente bajar `MIN_CONFIDENCE` en `.env` (mínimo recomendado: 0.55).

### NewsAPI: "rateLimited" o sin noticias
→ El plan gratuito tiene 100 requests/día. Con 2 símbolos y ciclo de 4h = ~12 requests/día (bien dentro del límite). Si hay más símbolos, considerar aumentar `CYCLE_INTERVAL_HOURS`.

### Señales acumulándose en pending_signals.json
→ bot1 está caído o ngrok no está activo. Levantar bot1 y al próximo ciclo se reenviarán automáticamente.

---

## Instalación en Linux (Ubuntu 20.04+)

```bash
# Instalar Python 3.11
sudo apt update && sudo apt install python3.11 python3.11-venv

# Clonar y configurar
git clone https://github.com/skeny65/Trading-agente-01.git
cd Trading-agente-01
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # editar credenciales

# Ejecutar
python agente01.py
```

**Como servicio systemd:**

```ini
# /etc/systemd/system/agente01.service
[Unit]
Description=agente01 Financial Research Agent
After=network.target

[Service]
Type=simple
User=tu_usuario
WorkingDirectory=/ruta/a/Trading-agente-01
ExecStart=/ruta/a/Trading-agente-01/venv/bin/python agente01.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable agente01
sudo systemctl start agente01
sudo journalctl -u agente01 -f  # ver logs en tiempo real
```
