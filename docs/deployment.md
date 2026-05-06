# Guía de Despliegue — agente01 (SPY Specialist)

## Requisitos Previos

- Python 3.11 o superior
- bot1 (Trading-bot) corriendo en `127.0.0.1:8000` con endpoint `/webhook/bot2`
- Cuenta en Anthropic Console (https://console.anthropic.com) — **ANTHROPIC_API_KEY** requerida
- Cuenta gratuita en FRED (https://fred.stlouisfed.org) — **FRED_API_KEY** recomendada
- Cuenta gratuita en NewsAPI.org (opcional — para VADER sentiment)
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
- `anthropic` — SDK oficial Claude AI (motor de decisión)
- `yfinance` — datos de mercado Yahoo Finance (multi-timeframe, precios, VIX)
- `ta` — indicadores técnicos (RSI, MACD, Bollinger Bands)
- `vaderSentiment` — análisis de sentimiento NLP (corre local)
- `openpyxl` — registro en trade_log.xlsx
- `requests` ya incluye soporte para Twelve Data (REST API pura, sin librería adicional)

### 4. Configurar credenciales

```bash
copy .env.example .env
```

Editar `.env` con los valores correctos (ver [environment_variables.md](environment_variables.md)).

**Mínimo requerido para operar:**
```
ANTHROPIC_API_KEY=sk-ant-api03-...
WEBHOOK_SECRET=mismo_secreto_que_bot1_minimo_32_chars
```

**Recomendado para análisis completo:**
```
FRED_API_KEY=tu_clave_fred
NEWSAPI_KEY=tu_clave_newsapi
TWELVE_DATA_API_KEY=tu_clave_twelvedata   # fuente de precios paralela a Yahoo
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

Ejecuta el ciclo SPY Specialist completo (6 dimensiones + Claude AI) en DRY_RUN — nunca envía webhook a bot1. Muestra scores por dimensión, resultado del pipeline de filtros, razonamiento de Claude y el payload que se enviaría si fuera APPROVE.

### 6b. Prueba de integración completa (envía webhook real a bot1)

```bash
python test_integration.py
```

Igual que `run_analysis.py` pero **sí envía el webhook a bot1** y escribe la fila en `logs/trade_log.xlsx` y `state/decision_log.jsonl`. Útil para verificar la integración end-to-end antes de dejar el agente en producción. Confirma que bot1 recibe la señal y que los logs se escriben correctamente.

### 7. Ejecutar en modo DRY_RUN (ciclo automático)

Asegúrate de que `.env` tiene `DRY_RUN=true`, luego:

```bash
python agente01.py
```

Deberías ver logs del ciclo completo. Los resultados se guardan en `logs/trade_log.xlsx` (con las 6 dimensiones y el razonamiento de Claude) y en `logs/YYYY-MM-DD_HH-MM-SS.json`.

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

1. Presionar `Win + R` → escribir `shell:startup` → Enter
2. Copiar el acceso directo de `start_agente01.bat` en esa carpeta
3. El agente arranca automáticamente con cada reinicio del PC

---

## Configuración de Ambos Bots en Paralelo

**Ventana 1 — bot1 (Trading-bot):**
```bash
cd C:\Users\kenyb\Desktop\GEMINI\Trading-bot
.\venv\Scripts\activate
python bot.py
```

**Ventana 2 — agente01:**
```bash
start_agente01.bat
```

---

## Verificación Post-arranque

### Logs esperados al iniciar

```
2026-04-27 09:45:00 [INFO] agente01 - agente01 SPY Specialist iniciado | modo=DRY RUN | symbol=SPY
2026-04-27 09:45:00 [INFO] agente01 - Ciclo cada 60min | umbral=0.72 | dims_min=5/6 | cooldown=24h
2026-04-27 09:45:00 [INFO] agente01 - [PRIORITY] INICIO DE CICLO | id=2026-04-27_09-45-00
2026-04-27 09:45:01 [INFO] analysis.spy_cycle - SPY: iniciando análisis 6 dimensiones
2026-04-27 09:45:02 [INFO] research.macro.fred_client - Macro: CPI=3.1% | yield_spread=+0.15% | macro_score=0.62
2026-04-27 09:45:03 [INFO] research.technical.multi_tf - Técnico: 1D=bullish, 4H=bullish, 1H=neutral | bullish_count=2 | score=0.81
2026-04-27 09:45:04 [INFO] research.components.spy_holdings - Componentes: 8/10 holdings+ | 9/11 sectores+ | score=0.74
2026-04-27 09:45:05 [INFO] research.sentiment - Sentimiento: VIX_term=contango | P/C=0.72 | F&G=65 | vader=+0.52 | score=0.73
2026-04-27 09:45:06 [INFO] research.events - Eventos: FOMC en 18d | sin eventos < 24h | mult=1.0 | score=0.80
2026-04-27 09:45:07 [INFO] research.cross_asset - Cross-assets: DXY=-0.3% TLT=+0.5% QQQ=+1.2% | score=0.78
2026-04-27 09:45:07 [INFO] analysis.filters - TOTAL=0.733 | dims_passing=6/6 | gate=PASS
2026-04-27 09:45:08 [INFO] analysis.claude_analyst - Claude: APPROVE | size=12% | trail=4.0% | cache_hit=True
2026-04-27 09:45:08 [INFO] agente01 - APPROVE [SPY]: BUY | confidence=0.733 | size=12% | trail=4.0% | dims=6/6
2026-04-27 09:45:08 [INFO] sender.webhook_client - [DRY_RUN] Webhook NO enviado — BUY SPY
2026-04-27 09:45:09 [INFO] excel_logger - trade_log.xlsx: +1 fila(s) guardadas
2026-04-27 09:45:09 [INFO] agente01 - Reporte guardado -> logs/2026-04-27_09-45-00.json
2026-04-27 09:45:09 [INFO] agente01 - FIN DE CICLO | 9.2s | aprobados=['SPY'] | salidas=[]
2026-04-27 09:45:09 [INFO] agente01 - Scheduler activo - proximo ciclo en 60min
```

### Verificar archivos de estado

```powershell
# Ver posición SPY abierta
Get-Content state\open_positions.json

# Ver últimas 5 decisiones
Get-Content state\decision_log.jsonl | Select-Object -Last 5

# Ver señales pendientes de reenvío
Get-Content state\pending_signals.json

# Ver el Excel con todos los análisis (6 dimensiones + claude_reasoning)
# Abrir directamente: logs\trade_log.xlsx
```

### Verificar trade_log.xlsx

El archivo `logs/trade_log.xlsx` se crea automáticamente al primer ciclo con mercado abierto. Cada fila es un ciclo SPY analizado con 47 columnas incluyendo las 6 dimensiones y el razonamiento de Claude. Permite filtrar por:
- `decision = APPROVE` → ver todas las señales generadas
- `webhook_status = sent` → ver señales realmente enviadas a bot1
- `dim_technical < 0.55` → ciclos donde el técnico fue la dimensión débil

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

### Error: "Variables de entorno faltantes: ANTHROPIC_API_KEY"
→ El archivo `.env` no tiene la clave de Anthropic. Obtenerla en https://console.anthropic.com y agregarla al `.env`.

### Error: "Variables de entorno faltantes: WEBHOOK_SECRET"
→ El archivo `.env` no existe o le falta la variable. Copiar `.env.example` a `.env` y rellenar.

### Error: "bot1 no disponible" en los logs
→ bot1 no está corriendo. Iniciar bot1 primero en otra ventana.

### HTTP 401 de bot1
→ `WEBHOOK_SECRET` en agente01 no coincide con el de bot1. Verificar ambos `.env`.

### Claude retorna siempre NO_SIGNAL
→ Verificar que `ANTHROPIC_API_KEY` es válida. Revisar logs de `analysis.claude_analyst` para el error exacto. El fallback es APPROVE cuando Claude falla — si Claude responde pero veta, revisar el razonamiento en `claude_reasoning` del Excel.

### FRED API sin datos (macro_score siempre 0.5)
→ Verificar `FRED_API_KEY`. La dimensión Macro usa score neutral (0.5) como fallback — el agente sigue funcionando pero sin datos macro reales. Obtener clave gratuita en fred.stlouisfed.org.

### Score siempre bajo (ciclos sin señales)
→ Normal en mercados con macro restrictiva o VIX elevado. Revisar el Excel para identificar qué dimensión puntúa bajo consistentemente. No bajar `MIN_CONFIDENCE` por debajo de 0.68 — el gate de dimensiones es igualmente importante.

### NewsAPI: "rateLimited" o sin noticias
→ El plan gratuito tiene 100 requests/día. El VADER sentiment usará fallback neutral. No afecta las otras 5 dimensiones.

### trade_log.xlsx no se actualiza
→ Verificar que el archivo no esté abierto en Excel. Cerrarlo — el próximo ciclo escribirá normalmente.

### Señales acumulándose en pending_signals.json
→ bot1 está caído. Levantarlo — al próximo ciclo se reenviarán automáticamente.

### CNN Fear & Greed devuelve error 418
→ Bloqueo anti-bot temporal. El agente usa fallback de 50.0 (Neutral) automáticamente. Solo afecta 1 sub-fuente de la dimensión Sentimiento.

### Yahoo Finance devuelve Too Many Requests
→ Rate limiting temporal. El agente usa fallbacks por dimensión y espera al próximo ciclo. Afecta principalmente dimensiones Técnico y Cross-Assets.

### VIX term structure siempre "flat"
→ Los futuros VX1/VX2 pueden no estar disponibles en yfinance todo el tiempo. "flat" (score 0.55) es el fallback correcto.

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
nano .env  # editar credenciales (ANTHROPIC_API_KEY, FRED_API_KEY, WEBHOOK_SECRET)

# Probar análisis manual (SPY Specialist — 6 dimensiones)
python run_analysis.py

# Ejecutar
python agente01.py
```

**Como servicio systemd (arranque automático):**

```ini
# /etc/systemd/system/agente01.service
[Unit]
Description=agente01 SPY Specialist Research Agent
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

---

## Costos Estimados por Ciclo (modo LIVE)

| Servicio | Costo estimado | Notas |
|---|---|---|
| **Claude AI (Haiku)** | ~$0.0002 / ciclo | Con prompt caching activo (~85% cache hit) |
| **FRED API** | Gratuito | Sin límite práctico |
| **NewsAPI** | Gratuito | 100 req/día (plan free) |
| **yfinance / Yahoo** | Gratuito | Rate limiting ocasional |
| **CBOE / CNN** | Gratuito | Endpoints públicos |

Con 6.5h de mercado y ciclos de 60min ≈ 7 ciclos/día → **~$0.0014/día** de costo Claude.
