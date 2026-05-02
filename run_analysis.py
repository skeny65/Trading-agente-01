"""
run_analysis.py — Ejecuta un ciclo SPY Specialist completo ignorando el horario de mercado.
Util para probar el agente fuera del horario de trading.
Siempre corre en DRY_RUN: nunca envia webhook real a bot1.
"""
import json
import sys
import io
from datetime import datetime, timezone

# Forzar UTF-8 en consolas Windows (cmd/PowerShell)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
config.DRY_RUN = True

from analysis.spy_cycle import run as spy_cycle_run
from sender import signal_formatter

SEP  = "=" * 65
SEP2 = "-" * 65


def run_analysis() -> None:
    started_at = datetime.now(timezone.utc)
    print(f"\n{SEP}")
    print(f"  SPY SPECIALIST — ANALISIS COMPLETO")
    print(f"  {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Modo: DRY_RUN | Symbol: {config.SYMBOL}")
    print(f"  Umbral: {config.MIN_CONFIDENCE} | Dims min: {config.MIN_DIMENSIONS_PASSING}/6")
    print(f"  Claude model: {config.CLAUDE_MODEL}")
    print(SEP)

    print("\n  Ejecutando pipeline SPY Specialist (6 dimensiones)...")
    print("  Esto puede tardar 10-30 segundos mientras se consultan las fuentes.\n")

    result = spy_cycle_run(config.SYMBOL)

    # ── Dimensiones ─────────────────────────────────────────────────────────────
    print(f"{SEP2}")
    print(f"  DIMENSIONES DE ANALISIS")
    print(SEP2)

    dims = result.dimension_scores
    if dims:
        weights = {
            "macro":       0.25,
            "technical":   0.20,
            "components":  0.20,
            "sentiment":   0.15,
            "events":      0.10,
            "cross_asset": 0.10,
        }
        names = {
            "macro":       "Macro       (FRED: CPI, NFP, yield curve)",
            "technical":   "Tecnico     (1D/4H/1H: RSI, MACD, BB, SMA200)",
            "components":  "Componentes (top-10 holdings + 11 sectores SPDR)",
            "sentiment":   "Sentimiento (VIX term + P/C + Fear&Greed + VADER)",
            "events":      "Eventos     (FOMC + calendario + Reuters)",
            "cross_asset": "Cross-Asset (DXY, TLT, HYG, QQQ, GLD, BTC)",
        }
        total_weighted = 0.0
        for key, w in weights.items():
            score = getattr(dims, key, 0.0) or 0.0
            contrib = score * w
            total_weighted += contrib
            flag = " OK" if score > 0.55 else " --"
            print(f"  {names[key]:<48} {score:.3f} x {w:.0%} = {contrib:.3f}{flag}")
        print(f"  {'-'*62}")
        print(f"  {'SCORE TOTAL':<48} {total_weighted:.3f}")
    else:
        print("  (dimensiones no disponibles)")

    # ── Filtros ──────────────────────────────────────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  RESULTADO DEL PIPELINE DE FILTROS")
    print(SEP2)

    fr = result.filter_result
    if fr:
        dims_passing = fr.dimensions_passing
        print(f"  Dimensiones > 0.55 : {dims_passing}/6  (minimo: {config.MIN_DIMENSIONS_PASSING})")
        print(f"  Score ajustado     : {fr.total_score:.3f}")
        if hasattr(fr, 'score_multiplier'):
            print(f"  Multiplicador      : x{fr.score_multiplier:.2f}  (eventos proximos)")
        print(f"  Gate aprobacion    : {'PASS ✓' if fr.approved else 'FAIL ✗'}")
        if not fr.approved and hasattr(fr, 'reason'):
            print(f"  Razon rechazo      : {fr.reason}")

    # ── VIX y trailing ──────────────────────────────────────────────────────────
    print(f"\n{SEP2}")
    print(f"  MARKET SNAPSHOT")
    print(SEP2)
    print(f"  VIX           : {result.vix_value:.2f}  ({result.vix_regime})")
    trail = signal_formatter.get_trail_config(result.vix_regime)
    print(f"  Trail config  : {trail['trail_percent']}% trail | "
          f"TP={trail['take_profit_pct']}% | max {trail['max_holding_days']}d")

    # ── Claude reasoning ─────────────────────────────────────────────────────────
    if result.claude_reasoning:
        print(f"\n{SEP2}")
        print(f"  RAZONAMIENTO CLAUDE AI")
        print(SEP2)
        # Wrap largo texto
        reasoning = result.claude_reasoning
        for i in range(0, len(reasoning), 70):
            print(f"  {reasoning[i:i+70]}")

    # ── Decision final ───────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    decision_icon = ">>> APPROVE <<<" if result.decision == "APPROVE" else "    NO_SIGNAL   "
    print(f"  DECISION FINAL: {decision_icon}")
    print(SEP)
    print(f"  Symbol     : {result.symbol}")
    print(f"  Decision   : {result.decision}")
    print(f"  Confidence : {result.confidence:.3f}")
    print(f"  Size       : {result.size:.0%} del capital")
    print(f"  Trail      : {result.trail_percent}%")
    print(f"  VIX regime : {result.vix_regime}")
    print(f"  Reason     : {result.reason}")

    # ── Payload ──────────────────────────────────────────────────────────────────
    if result.decision == "APPROVE":
        from sender.signal_formatter import build_spy_payload
        payload = build_spy_payload(result, result.vix_regime)
        print(f"\n{SEP}")
        print(f"  PAYLOAD QUE SE ENVIARIA A BOT1 (DRY_RUN — no enviado)")
        print(SEP)
        print(json.dumps(payload, indent=4, ensure_ascii=False, default=str))

    print(f"\n{SEP}")
    print(f"  [DRY_RUN] Ningun webhook fue enviado a bot1.")
    print(f"  Para ejecutar en modo automatico: python agente01.py")
    print(SEP)


if __name__ == "__main__":
    try:
        config.validate()
    except EnvironmentError as e:
        print(f"[ERROR] Configuracion invalida: {e}")
        sys.exit(1)
    run_analysis()
