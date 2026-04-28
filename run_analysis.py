"""
run_analysis.py — Ejecuta un ciclo de analisis completo ignorando el horario de mercado.
Util para probar el agente fuera del horario de trading (9:30-16:00 ET).
Siempre corre en DRY_RUN: nunca envia el webhook real.
"""
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from analysis import decision_engine, opportunity_scorer, sentiment_analyzer
from research import macro_indicators, market_data, news_fetcher
from sender import signal_formatter

# Forzar DRY_RUN para este script
config.DRY_RUN = True

SEP  = "=" * 60
SEP2 = "-" * 60


def _pprint(label: str, data: dict) -> None:
    print(f"\n{label}")
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def run_analysis() -> None:
    started_at = datetime.now(timezone.utc)
    print(f"\n{SEP}")
    print(f"  ANALISIS FORZADO — {started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Modo: DRY_RUN (no se envia ningun webhook)")
    print(f"  Watchlist: {config.WATCHLIST}")
    print(SEP)

    # ── 1. Macro ──────────────────────────────────────────────────────────────
    print("\n[1/3] Obteniendo contexto macro...")
    macro = macro_indicators.get_macro_context()
    print(f"  Fear & Greed : {macro.fear_greed_score} ({macro.fear_greed_label})")
    print(f"  VIX          : {macro.vix:.2f} ({macro.vix_regime})")
    print(f"  Macro Bias   : {macro.macro_bias}")

    # ── 2. Precios ────────────────────────────────────────────────────────────
    print("\n[2/3] Obteniendo datos de mercado...")
    quotes = market_data.get_quotes(config.WATCHLIST)

    # ── 3. Por simbolo ────────────────────────────────────────────────────────
    print("\n[3/3] Analizando simbolos...")
    results = []

    for symbol in config.WATCHLIST:
        print(f"\n{SEP2}")
        print(f"  SIMBOLO: {symbol}")
        print(SEP2)

        if symbol not in quotes:
            print(f"  [!] Sin datos de mercado para {symbol} — saltando")
            continue

        quote     = quotes[symbol]
        headlines = news_fetcher.fetch(symbol, hours=6)
        sentiment = sentiment_analyzer.analyze(headlines)
        score     = opportunity_scorer.calculate(quote, sentiment, macro)
        result    = decision_engine.evaluate(symbol, quote, sentiment, macro, score)

        # Mostrar datos
        print(f"\n  Precio     : ${quote.price:.2f}  ({quote.change_pct:+.2f}%)")
        print(f"  SMA20      : ${quote.sma20:.2f}  (precio vs SMA20: {quote.price_vs_sma20:+.2f}%)")
        print(f"  Tendencia  : {quote.trend}")
        print(f"  Vol Ratio  : {quote.volume_ratio:.2f}x")

        print(f"\n  Titulares  : {sentiment.headline_count} en ultimas 6h")
        for h in headlines[:3]:
            print(f"    - {h.title[:80]}")
        if len(headlines) > 3:
            print(f"    ... y {len(headlines)-3} mas")

        print(f"\n  Sentiment  : {sentiment.compound:+.3f} ({sentiment.label})")
        print(f"  Pos/Neg    : {sentiment.positive_ratio:.0%} positivo / {sentiment.negative_ratio:.0%} negativo")

        print(f"\n  SCORE BREAKDOWN:")
        print(f"    sentiment : {score.sentiment:.3f} x 30% = {score.sentiment * 0.30:.3f}")
        print(f"    trend     : {score.trend:.3f} x 30% = {score.trend * 0.30:.3f}")
        print(f"    macro     : {score.macro:.3f} x 25% = {score.macro * 0.25:.3f}")
        print(f"    vix       : {score.vix:.3f} x 15% = {score.vix * 0.15:.3f}")
        print(f"    TOTAL     : {score.total:.3f}  (umbral: {config.MIN_CONFIDENCE})")

        print(f"\n  DECISION    : {result.decision.value}")
        print(f"  Action      : {result.action}")
        print(f"  Confidence  : {result.confidence:.3f}")
        print(f"  Size        : {result.size}")
        print(f"  Reason      : {result.reason}")

        if result.decision.value == "APPROVE":
            payload = signal_formatter.build_payload(result)
            print(f"\n  {'*'*50}")
            print(f"  PAYLOAD QUE SE ENVIARIA POR WEBHOOK:")
            print(f"  {'*'*50}")
            print(json.dumps(payload, indent=4, ensure_ascii=False, default=str))

        results.append({
            "symbol":   symbol,
            "decision": result.decision.value,
            "score":    score.total,
            "action":   result.action,
            "reason":   result.reason,
        })

    # ── Resumen ───────────────────────────────────────────────────────────────
    print(f"\n{SEP}")
    print("  RESUMEN DEL CICLO")
    print(SEP)
    for r in results:
        icon = "✓ APPROVE" if r["decision"] == "APPROVE" else "  NO_SIGNAL"
        print(f"  {icon}  {r['symbol']:6s}  score={r['score']:.3f}  {r['reason'][:60]}")

    approved = [r for r in results if r["decision"] == "APPROVE"]
    print(f"\n  Aprobados  : {len(approved)}/{len(results)}")
    print(f"  Sin senal  : {len(results) - len(approved)}/{len(results)}")
    print(f"\n  [DRY_RUN] Ningun webhook fue enviado.")
    print(SEP)


if __name__ == "__main__":
    try:
        config.validate()
    except EnvironmentError as e:
        print(f"[ERROR] Configuracion invalida: {e}")
        sys.exit(1)
    run_analysis()
