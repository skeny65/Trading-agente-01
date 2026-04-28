# Guía de Despliegue — agente01

## Requisitos Previos

- Python 3.11 o superior
- bot1 (Trading-bot) corriendo en `127.0.0.1:8000` con endpoint `/webhook/bot2`
- Cuenta gratuita en NewsAPI.org (https://newsapi.org)
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

Las dependencias incluyen:
- `requests`, `python-dotenv`, `apscheduler`, `pytz` — core
- `yfinance` — datos de mercado
- `vaderSentiment` — análisis de sentimiento NLP (corre local)
- `openpyxl` — registro en trade_log.xlsx

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

### 6. Probar el análisis manualmente (sin esperar horario de mercado)

```bash
python run_analysis.py
```

Esto ejecuta un ciclo completo en DRY_RUN sin enviar webhooks. Permite verificar que todas las fuentes de datos funcionan y ver el payload que se enviaría.

### 7. Ejecutar en modo DRY_RUN (ciclo automático)

Asegúrate de que `.env` tiene `DRY_RUN=true`, luego:

```bash
python agente01.py
```

Deberías ver logs del ciclo completo. Los resultados se guardan en `logs/trade_log.xlsx` y en `logs/YYYY-MM-DD_HH-MM-SS.json`.

---

## Arranque Rápido con .bat (Windows)

El proyecto incluye `start_agente01.bat` en la raíz. Este archivo:
1. Activa el entorno virtual
2. Verifica que `.env` existe
3. Instala dependencias si faltan
4. Ejecuta `python agente01.py`

```bash
# Doble click en el explorador de archivos, o desde CMD:
start_agente01.bat
```

### Para arranque automático tras reinicio (24/7)

Agregar el `.bat` a la carpeta de inicio de Windows:

1. Presionar `Win + R` → escribir `shell:startup` → Enter
2. Copiar el acceso directo de `start_agente01.bat` en esa carpeta
3. Desde ese momento, el agente arranca automáticamente con cada reinicio del PC

---

## Configuración de Ambos Bots en Paralelo

Correr agente01 y bot1 simultáneamente usando dos ventanas de consola:

**Ventana 1 — bot1 (Trading-bot):**
```bash
cd C:\Users\kenyb\Desktop\GEMINI\Trading-bot
.\venv\Scripts\activate
python bot.py
```

**Ventana 2 — agente01:**
```bash
# O directamente:
start_agente01.bat
```

---

## Verificación Post-arranque

### Logs esperados al iniciar

```
2026-04-27 08:30:00 [INFO] agente01 - agente01 iniciado | modo=DRY RUN | watchlist=['SPY', 'QQQ', 'IWM', 'DIA', 'XLK', 'XLF', 'XLE', 'XLV']
2026-04-27 08:30:00 [INFO] agente01 - Ciclo cada 60min | umbral=0.70 | consenso=3/3 | cooldown=24h
2026-04-27 08:30:00 [INFO] agente01 - ============================================================
2026-04-27 08:30:00 [INFO] agente01 - INICIO DE CICLO | id=2026-04-27_08-30-00
2026-04-27 08:30:01 [INFO] research.macro_indicators - Macro: Fear&Greed=65 (Greed) | VIX=16.5 (moderate) | bias=bullish
2026-04-27 08:30:02 [INFO] research.market_data - SPY: $590.00 (+1.20%) | trend=strong_bullish | vol_ratio=1.40x
2026-04-27 08:30:03 [INFO] research.news_fetcher - SPY: 6 titulares en las ultimas 4h
2026-04-27 08:30:03 [INFO] analysis.sentiment_analyzer - Sentiment: compound=0.520 (positive) | pos=67% neg=8% | n=6
2026-04-27 08:30:03 [INFO] analysis.opportunity_scorer - Score [SPY]: total=0.813 | trend=1.00 sentiment=0.76 macro=0.65 vix=0.65
2026-04-27 08:30:03 [INFO] analysis.decision_engine - APPROVE [SPY]: BUY | confidence=0.813 | size=0.05 | trend_strength=strong_bullish
2026-04-27 08:30:03 [INFO] sender.webhook_client - [DRY_RUN] Webhook NO enviado — BUY SPY
2026-04-27 08:30:45 [INFO] agente01 - trade_log.xlsx: +8 fila(s) guardadas
2026-04-27 08:30:45 [INFO] agente01 - Reporte guardado -> logs/2026-04-27_08-30-00.json
2026-04-27 08:30:45 [INFO] agente01 - FIN DE CICLO | 45.2s | aprobados=['SPY'] | salidas=[] | holding=[]
2026-04-27 08:30:45 [INFO] agente01 - Scheduler activo - proximo ciclo en 60min
```

### Verificar archivos de estado

```powershell
# Ver posiciones abiertas
Get-Content state\open_positions.json

# Ver últimas 5 decisiones
Get-Content state\decision_log.jsonl | Select-Object -Last 5

# Ver señales pendientes de reenvío
Get-Content state\pending_signals.json

# Ver el Excel con todos los análisis
# Abrir directamente: logs\trade_log.xlsx
```

### Verificar trade_log.xlsx

El archivo `logs/trade_log.xlsx` se crea automáticamente al primer ciclo con mercado abierto.
Cada fila es un símbolo analizado en un ciclo. Permite filtrar por:
- `decision = APPROVE` → ver todas las señales generadas
- `symbol = SPY` → ver historial completo de SPY
- `webhook_status = sent` → ver señales realmente enviadas a bot1

---

## Pasar a Modo LIVE

Cuando hayas verificado que el ciclo funciona correctamente en DRY_RUN:

1. Verificar que bot1 está en modo paper trading (`ALPACA_BASE_URL=https://paper-api.alpaca.markets/v2`)

2. Editar `.env`:
   ```
   DRY_RUN=false
   ```

3. Verificar que el `WEBHOOK_SECRET` coincide exactamente con el de bot1

4. Reiniciar agente01:
   ```bash
   start_agente01.bat
   ```

En modo LIVE, el `webhook_status` en el Excel mostrará `"sent"` cuando la señal llegue a bot1 y este responda `"executed"`.

---

## Solución de Problemas

### Error: "Variables de entorno faltantes: NEWSAPI_KEY"
→ El archivo `.env` no existe o le falta la variable. Copiar `.env.example` a `.env` y rellenar.

### Error: "bot1 no disponible" en los logs
→ bot1 no está corriendo. Iniciar bot1 primero en otra ventana.

### HTTP 401 de bot1
→ `WEBHOOK_SECRET` en agente01 no coincide con el de bot1. Verificar ambos `.env`.

### Score siempre bajo (ciclos sin señales)
→ Normal en mercados laterales o con alta volatilidad (VIX alto). Revisar el Excel para identificar qué componente puntúa bajo. Reducir `MIN_CONFIDENCE` de 0.70 a 0.68 puede ayudar — no bajar de 0.65.

### NewsAPI: "rateLimited" o sin noticias
→ El plan gratuito tiene 100 requests/día. Con 8 símbolos y ciclos de 1h durante 6.5h de mercado = hasta 52 requests/día (dentro del límite). Si hay problemas, verificar el uso en newsapi.org.

### trade_log.xlsx no se actualiza
→ Verificar que el archivo no esté abierto en Excel. Si lo está, cerrar Excel y el próximo ciclo escribirá normalmente.

### Señales acumulándose en pending_signals.json
→ bot1 está caído. Levantarlo — al próximo ciclo se reenviarán automáticamente.

### CNN Fear & Greed devuelve error 418
→ Bloqueo anti-bot temporal. El agente usa el fallback de 50.0 (Neutral) automáticamente.

### Yahoo Finance devuelve Too Many Requests
→ Rate limiting temporal (común si se hacen varias llamadas rápidas en testing). El agente espera al próximo ciclo. No es un error del código.

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

# Probar análisis manual
python run_analysis.py

# Ejecutar
python agente01.py
```

**Como servicio systemd (arranque automático):**

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
