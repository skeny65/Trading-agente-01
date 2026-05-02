"""
test_integration.py — Prueba de integracion end-to-end.
Corre el ciclo SPY Specialist completo (Claude AI real), envia el resultado
a bot1 via webhook, y escribe la fila en trade_log.xlsx.
Ignora el horario de mercado.

Uso:
    python test_integration.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# UTF-8 en consola Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
config.DRY_RUN = False  # envio real a bot1

from analysis.spy_cycle import run as spy_cycle_run
from excel_logger import append_excel_rows
from sender import signal_formatter, webhook_client

SEP  = "=" * 65
SEP2 = "-" * 65

# ─── Meta del ciclo (igual que en agente01.py) ──────────────────────────────
started_at  = datetime.now(timezone.utc)
cycle_id    = started_at.strftime("%Y-%m-%d_%H-%M-%S")
cycle_meta  = {
    "timestamp_utc":  started_at.isoformat(),
    "cycle_id":       cycle_id,
    "mode":           "TEST",
    "priority_cycle": False,
}

print(f"\n{SEP}")
print(f"  PRUEBA DE INTEGRACION REAL — agente01 <-> bot1")
print(f"  {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"  Claude API: REAL | Webhook: REAL | Excel: REAL")
print(SEP)

# ─── PASO 1: Investigacion SPY Specialist ───────────────────────────────────
print("\n[1/4] Ejecutando investigacion SPY Specialist...")
print("      (Claude AI + FRED + yfinance + eventos — 20-40s)\n")

t0 = datetime.now(timezone.utc)
result = spy_cycle_run(config.SYMBOL)
elapsed = (datetime.now(timezone.utc) - t0).total_seconds()

print(f"\n{SEP2}")
print(f"  RESULTADO  ({elapsed:.1f}s)")
print(SEP2)

dims = result.dimension_scores
weights = {"macro":0.25,"technical":0.20,"components":0.20,
           "sentiment":0.15,"events":0.10,"cross_asset":0.10}
names = {"macro":"Macro","technical":"Tecnico","components":"Componentes",
         "sentiment":"Sentimiento","events":"Eventos","cross_asset":"Cross-Asset"}
total = 0.0
if dims:
    for key, w in weights.items():
        s = getattr(dims, key, 0.0) or 0.0
        c = s * w
        total += c
        flag = "OK" if s > 0.55 else "--"
        print(f"  {flag}  {names[key]:<14} {s:.3f} x {w:.0%} = {c:.3f}")
    print(f"       {'TOTAL':<14} {total:.3f}  (umbral: {config.MIN_CONFIDENCE})")

fr = result.filter_result
if fr:
    print(f"\n  Gate       : {'PASS' if fr.approved else 'FAIL'} — {fr.reason}")
    print(f"  Dims OK    : {fr.dimensions_passing}/6")

print(f"  VIX        : {result.vix_value:.2f} ({result.vix_regime})")
print(f"  DECISION   : {result.decision}")
print(f"  Confidence : {result.confidence:.3f}")
if result.size:
    print(f"  Size       : {result.size:.0%} del capital")
print(f"  Trail      : {result.trail_percent}%")

if result.claude_reasoning:
    print(f"\n  Claude AI:")
    for chunk in [result.claude_reasoning[i:i+68] for i in range(0, len(result.claude_reasoning), 68)]:
        print(f"    {chunk}")

# ─── PASO 2: Enviar webhook a bot1 ──────────────────────────────────────────
print(f"\n{SEP2}")
print(f"  ENVIANDO A BOT1")
print(SEP2)

if result.decision == "APPROVE":
    payload = signal_formatter.build_spy_payload(result, result.vix_regime)
    print(f"  Tipo : BUY payload (APPROVE)")
else:
    payload = {
        "timestamp": started_at.isoformat(),
        "status":    "no_signal",
        "processed": False,
        "reason":    f"Score {result.confidence:.3f} | {result.reason}",
        "signal":    None,
    }
    print(f"  Tipo : NO_SIGNAL payload")

print(f"  URL  : {config.WEBHOOK_URL}")
print(f"\n[2/4] Enviando webhook...")
response = webhook_client.send(payload)
webhook_status = "sent" if response.get("status") not in ("failed","error") else "failed"
print(f"\n  Respuesta bot1: {json.dumps(response, ensure_ascii=False)}")

# ─── PASO 3: Escribir al Excel ───────────────────────────────────────────────
print(f"\n{SEP2}")
print(f"  GUARDANDO EN EXCEL")
print(SEP2)

# Construir la fila con todos los campos del SPY Specialist
dim  = result.dimension_scores
row = {
    # Meta
    "timestamp_utc":     cycle_meta["timestamp_utc"],
    "cycle_id":          cycle_meta["cycle_id"],
    "mode":              cycle_meta["mode"],
    "priority_cycle":    cycle_meta["priority_cycle"],
    "symbol":            result.symbol,
    "status":            "ANALYZED",
    "decision":          result.decision,
    "action":            result.action,
    "confidence":        result.confidence,
    "size":              result.size,
    "reason":            result.reason,
    "webhook_status":    webhook_status,
    # VIX y trailing
    "vix":               result.vix_value,
    "vix_regime":        result.vix_regime,
    "trail_percent":     result.trail_percent,
    "take_profit_pct":   signal_formatter.get_trail_config(result.vix_regime)["take_profit_pct"],
    "max_holding_days":  signal_formatter.get_trail_config(result.vix_regime)["max_holding_days"],
    # 6 dimensiones
    "dim_macro":         round(dim.macro,       4) if dim else "",
    "dim_technical":     round(dim.technical,   4) if dim else "",
    "dim_components":    round(dim.components,  4) if dim else "",
    "dim_sentiment":     round(dim.sentiment,   4) if dim else "",
    "dim_events":        round(dim.events,      4) if dim else "",
    "dim_cross_asset":   round(dim.cross_asset, 4) if dim else "",
    "dimensions_passing": fr.dimensions_passing if fr else "",
    "score_total":       round(total, 4),
    # Claude reasoning
    "claude_reasoning":  result.claude_reasoning,
}

print(f"[3/4] Escribiendo fila en trade_log.xlsx...")
append_excel_rows([row])

# Verificar que se escribio
xl_file = Path("logs/trade_log.xlsx")
if xl_file.exists():
    import openpyxl
    wb = openpyxl.load_workbook(xl_file)
    ws = wb.active
    print(f"  trade_log.xlsx : {ws.max_row - 1} fila(s) registradas")
    print(f"  Ubicacion      : {xl_file.resolve()}")

# ─── PASO 4: Verificar decision_log.jsonl ───────────────────────────────────
print(f"\n[4/4] Registrando en decision_log.jsonl...")
log_entry = {
    "ts":              started_at.isoformat(),
    "cycle_id":        cycle_id,
    "symbol":          result.symbol,
    "decision":        result.decision,
    "confidence":      result.confidence,
    "size":            result.size,
    "reason":          result.reason,
    "claude_reasoning": result.claude_reasoning,
    "vix_regime":      result.vix_regime,
    "vix_value":       result.vix_value,
    "dimension_scores": {
        "macro":       round(dim.macro,       4) if dim else None,
        "technical":   round(dim.technical,   4) if dim else None,
        "components":  round(dim.components,  4) if dim else None,
        "sentiment":   round(dim.sentiment,   4) if dim else None,
        "events":      round(dim.events,      4) if dim else None,
        "cross_asset": round(dim.cross_asset, 4) if dim else None,
    },
    "dimensions_passing": fr.dimensions_passing if fr else None,
    "webhook_status":  webhook_status,
    "bot1_response":   response,
    "mode":            "TEST",
}

log_file = Path("state/decision_log.jsonl")
with open(log_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(log_entry, ensure_ascii=False, default=str) + "\n")
print(f"  decision_log.jsonl : entrada agregada")

# ─── Resumen ─────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
ok = webhook_status == "sent"
print(f"  INTEGRACION : {'OK' if ok else 'ERROR'}")
print(f"  Ciclo ID    : {cycle_id}")
print(f"  Decision    : {result.decision}  (score {result.confidence:.3f})")
print(f"  bot1        : {response.get('status', 'sin respuesta')}")
print(f"  Excel       : logs/trade_log.xlsx")
print(f"  Log         : state/decision_log.jsonl")
print(SEP)
print(f"\n  Abre logs/trade_log.xlsx para ver la fila completa con")
print(f"  las 6 dimensiones y el razonamiento de Claude.")
print()
