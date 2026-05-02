"""
Analisis SPY en tiempo real - todos los modulos de investigacion SPY specialist.
"""
import logging
import sys
from datetime import datetime, timezone

logging.basicConfig(level=logging.WARNING)

import config
config.DRY_RUN = True

SEP  = "=" * 65
SEP2 = "-" * 65

def fmt(v, decimals=2, suffix=""):
    if v is None:
        return "N/D"
    return f"{v:.{decimals}f}{suffix}"

def pct(v):
    if v is None:
        return "N/D"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"

print()
print(SEP)
print(f"  ANALISIS SPY - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print(f"  Modo: Especialista SPY | 6 dimensiones de analisis")
print(SEP)

# ── DIMENSION 1: MACRO (FRED) ─────────────────────────────────────────────────
print("\n[1/6] MACRO ECONOMICA (FRED API)...")
try:
    from research.macro.inflation import get_inflation_data
    from research.macro.employment import get_employment_data
    from research.macro.rates import get_rates_data
    from research.macro.fed_watch import get_fed_watch_data
    from analysis.dimension_scorers.macro_scorer import calculate as calc_macro

    infl   = get_inflation_data()
    empl   = get_employment_data()
    rate   = get_rates_data()
    fedw   = get_fed_watch_data()
    macro_s = calc_macro(infl.score, empl.score, rate.score, fedw.score,
                         rate.yield_curve_spread)

    print(f"  CPI YoY          : {fmt(infl.cpi_yoy,2,'%')} | Core PCE YoY: {fmt(infl.core_pce_yoy,2,'%')}")
    print(f"  Inflacion        : {infl.label} (score={infl.score:.2f})")
    print(f"  Desempleo        : {fmt(empl.unemployment_rate,1,'%')} | NFP cambio: {fmt(empl.nfp_mom_change,1,'k')}")
    print(f"  Empleo           : {empl.label} (score={empl.score:.2f})")
    print(f"  Fed Funds Rate   : {fmt(rate.fed_funds_rate,2,'%')}")
    print(f"  Yield curve 10Y-2Y: {fmt(rate.yield_curve_spread,3)} ({rate.curve_shape})")
    print(f"  Postura Fed      : {fedw.fed_stance} | hike={fedw.prob_hike:.0%} cut={fedw.prob_cut:.0%} hold={fedw.prob_hold:.0%}")
    print(f"  >> MACRO SCORE   : {macro_s.total:.3f}  [{macro_s.label.upper()}]")
    if macro_s.veto:
        print(f"  !! VETO MACRO activo (curva invertida + macro deteriorada)")
except Exception as e:
    print(f"  ERROR macro: {e}")
    macro_s = type("M", (), {"total": 0.5, "veto": False, "label": "neutral",
                             "yield_curve_spread": None})()

# ── DIMENSION 2: EVENTOS ──────────────────────────────────────────────────────
print(f"\n[2/6] EVENTOS PROGRAMADOS (proximas 48h)...")
try:
    from research.events.economic_calendar import get_upcoming_high_impact_events, get_defensive_mode
    from research.events.geopolitics_news import get_geopolitics_signal
    from analysis.dimension_scorers.events_scorer import calculate as calc_events

    events    = get_upcoming_high_impact_events(hours_ahead=48)
    defensive = get_defensive_mode(events)
    geo       = get_geopolitics_signal()
    events_s  = calc_events(defensive["score_multiplier"], defensive["veto"],
                             geo.score, defensive["reason"])

    if events:
        for ev in events[:3]:
            print(f"  ALERTA {ev.impact}: '{ev.event}' en {ev.hours_away:.1f}h")
    else:
        print(f"  OK - Sin eventos de alto impacto en las proximas 48h")
    print(f"  Geopolitica      : {geo.risk_level} (score={geo.score:.2f})")
    print(f"  Modo defensivo   : {defensive['reason']}")
    print(f"  Multiplicador    : {defensive['score_multiplier']:.2f}")
    print(f"  >> EVENTOS SCORE : {events_s.total:.3f}  [{'VETO' if events_s.veto else 'OK'}]")
except Exception as e:
    print(f"  ERROR eventos: {e}")
    events_s  = type("E", (), {"total": 0.8, "veto": False,
                               "score_multiplier": 1.0, "reason": "error_fallback"})()
    defensive = {"score_multiplier": 1.0, "veto": False, "reason": "error_fallback"}

# ── DIMENSION 3: TECNICO MULTI-TIMEFRAME ──────────────────────────────────────
print(f"\n[3/6] TECNICO MULTI-TIMEFRAME (1D / 4H / 1H)...")
try:
    from research.technical.multi_timeframe import get_multi_timeframe_analysis
    from analysis.dimension_scorers.technical_scorer import calculate as calc_technical

    tech   = get_multi_timeframe_analysis("SPY")
    tech_s = calc_technical(tech.overall_score, tech.bullish_count,
                             tech.rsi_veto, tech.sma200_veto, tech.atr_veto)

    above200 = "SOBRE SMA200" if tech.daily.above_sma200 else "BAJO SMA200 (!)"
    print(f"  Diario (1D)      : trend={tech.daily.trend} | RSI={fmt(tech.daily.rsi,1)} | {above200}")
    print(f"  4 Horas (4H)     : trend={tech.four_h.trend} | RSI={fmt(tech.four_h.rsi,1)}")
    print(f"  1 Hora (1H)      : trend={tech.one_h.trend} | RSI={fmt(tech.one_h.rsi,1)}")
    print(f"  Alineacion       : {tech.alignment.upper()} ({tech.bullish_count}/3 timeframes bullish)")
    if tech.key_levels.high_52w:
        print(f"  52w High / Low   : ${fmt(tech.key_levels.high_52w)} / ${fmt(tech.key_levels.low_52w)}")
        print(f"  Dist. al 52w H   : {pct(tech.key_levels.distance_to_52w_high)}")
    if tech.rsi_veto:    print(f"  !! VETO RSI > 75 (sobrecompra extrema)")
    if tech.sma200_veto: print(f"  !! VETO SMA200 (precio por debajo de la media de 200d)")
    if tech.atr_veto:    print(f"  !! ATR anomalo (volatilidad 2x su media de 30d)")
    print(f"  >> TECNICO SCORE : {tech_s.total:.3f}  [{tech.alignment.upper()}]")
except Exception as e:
    print(f"  ERROR tecnico: {e}")
    import traceback; traceback.print_exc()
    tech_s = type("T", (), {"total": 0.5, "rsi_veto": False,
                             "sma200_veto": False, "atr_veto": False})()
    tech   = type("T2", (), {"rsi_veto": False, "sma200_veto": False, "atr_veto": False})()

# ── DIMENSION 4: COMPONENTES ──────────────────────────────────────────────────
print(f"\n[4/6] COMPONENTES DEL INDICE (top 10 SPY + sectores)...")
try:
    from research.components.top_holdings import get_top_holdings_data
    from research.components.sectors import get_sector_breadth
    from research.components.earnings_calendar import get_earnings_data
    from analysis.dimension_scorers.components_scorer import calculate as calc_components

    holdings = get_top_holdings_data()
    sectors  = get_sector_breadth()
    earnings = get_earnings_data(hours_ahead=48)
    comp_s   = calc_components(holdings.score, sectors.score, earnings.veto_active)

    print(f"  Top 10 holdings  : {holdings.bullish_count}/{len(holdings.holdings)} alcistas | "
          f"retorno pond: {pct(holdings.weighted_avg_1d)}")
    top3 = sorted(holdings.holdings, key=lambda h: h.change_1d or 0, reverse=True)[:3]
    for h in top3:
        print(f"    {h.symbol:6s} ({h.weight:.1%}): {pct(h.change_1d)}")
    print(f"  Sectores verdes  : {sectors.green_count}/{sectors.total_count} | lider={sectors.leading_sector}")
    print(f"  Tech (XLK) lidera: {'SI' if sectors.tech_leading else 'NO'}")
    if earnings.veto_active:
        print(f"  !! VETO EARNINGS: {earnings.count_upcoming} top-10 con earnings en 48h")
    else:
        print(f"  Earnings proximos: {earnings.count_upcoming} (sin veto)")
    print(f"  >> COMPONENTES   : {comp_s.total:.3f}")
except Exception as e:
    print(f"  ERROR componentes: {e}")
    comp_s   = type("C", (), {"total": 0.5, "earnings_veto": False})()
    earnings = type("E2", (), {"veto_active": False})()

# ── DIMENSION 5: CROSS-ASSETS ─────────────────────────────────────────────────
print(f"\n[5/6] CORRELACIONES CRUZADAS (DXY / TLT / GLD / HYG / QQQ)...")
try:
    import yfinance as yf
    from research.cross_assets.correlations import get_cross_asset_data
    from analysis.dimension_scorers.cross_asset_scorer import calculate as calc_cross

    spy_hist = yf.Ticker("SPY").history(period="10d", interval="1d")
    spy_5d   = float((spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[-6] - 1) * 100) if len(spy_hist) >= 6 else None

    cross   = get_cross_asset_data(spy_change_5d=spy_5d)
    cross_s = calc_cross(cross.score, cross.divergences)

    def asset_chg(sym):
        a = cross.assets.get(sym)
        return pct(a.change_5d) if a and a.change_5d else "N/D"

    print(f"  SPY (5d)         : {pct(spy_5d)}")
    print(f"  DXY dolar (5d)   : {asset_chg('DX-Y.NYB')} | {'subiendo - presion' if cross.dxy_bullish else 'neutral/bajo'}")
    print(f"  TLT bonos (5d)   : {asset_chg('TLT')} | {'flight-to-safety' if cross.tlt_bullish else 'risk-on OK'}")
    print(f"  HYG high-yield   : {asset_chg('HYG')} | {'risk-on OK' if cross.hyg_bullish else 'reduciendo riesgo'}")
    print(f"  QQQ vs SPY       : {'Nasdaq lidera' if cross.qqq_leading else 'QQQ no lidera'} | {asset_chg('QQQ')}")
    if cross.divergences:
        for d in cross.divergences:
            print(f"  !! Divergencia: {d}")
    print(f"  >> CROSS-ASSETS  : {cross_s.total:.3f}")
except Exception as e:
    print(f"  ERROR cross-assets: {e}")
    cross_s = type("X", (), {"total": 0.5, "divergences": []})()
    cross   = type("X2", (), {"divergences": []})()

# ── DIMENSION 6: SENTIMIENTO ──────────────────────────────────────────────────
print(f"\n[6/6] SENTIMIENTO (Fear&Greed / VIX / Put-Call / Noticias)...")
try:
    from research.macro_indicators import get_macro_context
    from research.sentiment.vix_term_structure import get_vix_term_structure
    from research.sentiment.put_call_ratio import get_put_call_ratio
    from research.news_fetcher import fetch as fetch_news
    from analysis.sentiment_analyzer import analyze as analyze_sentiment
    from analysis.dimension_scorers.sentiment_scorer import calculate as calc_sentiment

    macro_ctx = get_macro_context()
    vix_term  = get_vix_term_structure()
    put_call  = get_put_call_ratio()
    headlines = fetch_news("SPY", hours=config.NEWS_LOOKBACK_HOURS)
    sent      = analyze_sentiment(headlines)

    fg_score   = macro_ctx.fear_greed_score / 100
    news_score = (sent.compound + 1) / 2
    sent_s     = calc_sentiment(fg_score, vix_term.score, put_call.score, news_score)

    print(f"  Fear & Greed     : {macro_ctx.fear_greed_score} ({macro_ctx.fear_greed_label})")
    print(f"  VIX spot         : {fmt(vix_term.vix,2)} | 9D={fmt(vix_term.vix9d,2)} | 3M={fmt(vix_term.vix3m,2)}")
    print(f"  VIX estructura   : {vix_term.structure.upper()}")
    pc_extra = ""
    if put_call.contrarian_bullish: pc_extra = " - PANICO EXTREMO (contrarian bullish)"
    if put_call.contrarian_bearish: pc_extra = " - EUFORIA EXTREMA (contrarian bearish)"
    print(f"  Put/Call ratio   : {fmt(put_call.ratio,2)} ({put_call.signal}){pc_extra}")
    print(f"  Noticias SPY     : {len(headlines)} titulares | VADER: {sent.compound:+.3f} ({sent.label})")
    if headlines:
        for h in headlines[:2]:
            title = h.title if hasattr(h, "title") else str(h)
            print(f"    - {title[:72]}")
    vix_regime = macro_ctx.vix_regime
    print(f"  VIX regime       : {vix_regime}")
    print(f"  >> SENTIMIENTO   : {sent_s.total:.3f}")

    from sender.signal_formatter import get_trail_config
    trail_cfg = get_trail_config(vix_regime)
except Exception as e:
    print(f"  ERROR sentimiento: {e}")
    import traceback; traceback.print_exc()
    sent_s    = type("S", (), {"total": 0.5})()
    vix_regime = "moderate"
    trail_cfg  = {"trail_percent": 4.0, "take_profit_pct": None, "max_holding_days": 10}
    macro_ctx  = type("M2", (), {"vix": 20.0, "vix_regime": "moderate",
                                  "fear_greed_score": 50, "fear_greed_label": "Neutral"})()

# ── SCORE FINAL + FILTROS ─────────────────────────────────────────────────────
print()
print(SEP)
print("  SCORE TOTAL Y FILTROS EN CASCADA")
print(SEP)

try:
    from analysis.filters import DimensionScores, evaluate as run_filters

    dim_scores = DimensionScores(
        macro       = macro_s.total,
        components  = getattr(comp_s, "total", 0.5),
        sentiment   = sent_s.total,
        technical   = tech_s.total,
        events      = events_s.total,
        cross_asset = cross_s.total,
    )

    print()
    print(f"  Dimension            Score   Peso   Aporte")
    print(f"  {'-'*48}")
    print(f"  Macro                {dim_scores.macro:.3f}   25%    {dim_scores.macro*0.25:.3f}")
    print(f"  Componentes          {dim_scores.components:.3f}   20%    {dim_scores.components*0.20:.3f}")
    print(f"  Sentimiento          {dim_scores.sentiment:.3f}   15%    {dim_scores.sentiment*0.15:.3f}")
    print(f"  Tecnico              {dim_scores.technical:.3f}   20%    {dim_scores.technical*0.20:.3f}")
    print(f"  Eventos              {dim_scores.events:.3f}   10%    {dim_scores.events*0.10:.3f}")
    print(f"  Cross-assets         {dim_scores.cross_asset:.3f}   10%    {dim_scores.cross_asset*0.10:.3f}")
    raw_total = (dim_scores.macro*0.25 + dim_scores.components*0.20 +
                 dim_scores.sentiment*0.15 + dim_scores.technical*0.20 +
                 dim_scores.events*0.10 + dim_scores.cross_asset*0.10)
    print(f"  {'-'*48}")
    print(f"  TOTAL                {raw_total:.3f}          umbral={config.MIN_CONFIDENCE}")

    result = run_filters(
        scores            = dim_scores,
        vix_regime        = vix_regime,
        events_veto       = events_s.veto,
        events_reason     = events_s.reason,
        events_multiplier = events_s.score_multiplier,
        earnings_veto     = getattr(comp_s, "earnings_veto", False),
        rsi_veto          = getattr(tech_s, "rsi_veto", False),
        sma200_veto       = getattr(tech_s, "sma200_veto", False),
        macro_veto        = macro_s.veto,
        trail_percent     = trail_cfg["trail_percent"],
    )
except Exception as e:
    print(f"  ERROR filtros: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── RESULTADO ─────────────────────────────────────────────────────────────────
print()
print(SEP)
if result.approved:
    print("  DECISION: COMPRAR SPY")
    print(f"  {'='*55}")
    print(f"  Score final      : {result.total_score:.3f}")
    print(f"  Dimensiones OK   : {result.dimensions_passing}/6 (minimo {config.MIN_DIMENSIONS_PASSING})")
    print(f"  Tamano posicion  : {result.size:.0%} del capital")
    print(f"  Trailing stop    : {trail_cfg['trail_percent']}%")
    if trail_cfg.get("take_profit_pct"):
        print(f"  Take profit      : {trail_cfg['take_profit_pct']}%")
    print(f"  Max holding      : {trail_cfg['max_holding_days']} dias")
    print(f"  VIX regime       : {vix_regime}")
    print(f"  Razon            : {result.reason}")
else:
    print("  DECISION: NO ENTRAR AHORA")
    print(f"  {'='*55}")
    print(f"  Score final      : {result.total_score:.3f}  (minimo {config.MIN_CONFIDENCE})")
    if result.veto_triggers:
        print(f"  VETOS ACTIVOS:")
        for v in result.veto_triggers:
            print(f"    X {v}")
    else:
        print(f"  Razon            : {result.reason}")
        if result.dimension_scores:
            ds = result.dimension_scores
            failing = [(n,v) for n,v in [
                ("Macro",ds.macro),("Componentes",ds.components),
                ("Sentimiento",ds.sentiment),("Tecnico",ds.technical),
                ("Eventos",ds.events),("Cross-asset",ds.cross_asset)
            ] if v < 0.55]
            if failing:
                print(f"  Dimensiones < 0.55: {', '.join(f'{n}({v:.3f})' for n,v in failing)}")

print()
print(f"  VIX={fmt(getattr(macro_ctx,'vix',0),2)} ({vix_regime}) | "
      f"Fear&Greed={getattr(macro_ctx,'fear_greed_score',50)} ({getattr(macro_ctx,'fear_greed_label','?')})")
print(f"  [DRY_RUN - ningun webhook enviado]")
print(SEP)
