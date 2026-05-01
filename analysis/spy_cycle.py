"""
Orquestador del ciclo SPY Specialist.

Ejecuta las 6 dimensiones de investigación, aplica el pipeline de
filtros en cascada y llama al motor Claude para la decisión final.
"""
import logging
from dataclasses import dataclass

import config

# ── Dimensión 1: Macro ────────────────────────────────────────────────────────
from research.macro.inflation import get_inflation_data
from research.macro.employment import get_employment_data
from research.macro.rates import get_rates_data
from research.macro.fed_watch import get_fed_watch_data

# ── Dimensión 2: Eventos ──────────────────────────────────────────────────────
from research.events.economic_calendar import get_upcoming_high_impact_events, get_defensive_mode
from research.events.geopolitics_news import get_geopolitics_signal

# ── Dimensión 3: Técnico ──────────────────────────────────────────────────────
from research.technical.multi_timeframe import get_multi_timeframe_analysis

# ── Dimensión 4: Componentes ──────────────────────────────────────────────────
from research.components.top_holdings import get_top_holdings_data
from research.components.sectors import get_sector_breadth
from research.components.earnings_calendar import get_earnings_data

# ── Dimensión 5: Cross-assets ─────────────────────────────────────────────────
from research.cross_assets.correlations import get_cross_asset_data

# ── Dimensión 6: Sentimiento ──────────────────────────────────────────────────
from research.sentiment.vix_term_structure import get_vix_term_structure
from research.sentiment.put_call_ratio import get_put_call_ratio
from research.macro_indicators import get_macro_context  # Fear&Greed + VIX spot
from research.news_fetcher import fetch as fetch_headlines
from analysis.sentiment_analyzer import analyze as analyze_sentiment

# ── Scorers ───────────────────────────────────────────────────────────────────
from analysis.dimension_scorers.macro_scorer import calculate as score_macro
from analysis.dimension_scorers.events_scorer import calculate as score_events
from analysis.dimension_scorers.technical_scorer import calculate as score_technical
from analysis.dimension_scorers.components_scorer import calculate as score_components
from analysis.dimension_scorers.cross_asset_scorer import calculate as score_cross_asset
from analysis.dimension_scorers.sentiment_scorer import calculate as score_sentiment

# ── Pipeline ──────────────────────────────────────────────────────────────────
from analysis.filters import DimensionScores, FilterResult, evaluate as filter_evaluate
from analysis.claude_analyst import ClaudeAnalysis, analyze as claude_analyze

logger = logging.getLogger(__name__)


@dataclass
class SpyCycleResult:
    decision: str           # "APPROVE" | "NO_SIGNAL"
    action: str             # "buy" | "none"
    confidence: float       # total weighted score
    size: float             # portfolio fraction
    trail_percent: float    # dynamic trailing stop
    reason: str             # filter reason
    claude_reasoning: str   # Claude's narrative
    symbol: str
    vix_regime: str
    vix_value: float
    filter_result: FilterResult
    dimension_scores: DimensionScores


def _trail_for_regime(vix_regime: str) -> float:
    return {
        "low":      config.TRAIL_PERCENT_LOW_VIX,
        "moderate": config.TRAIL_PERCENT_MODERATE_VIX,
        "high":     config.TRAIL_PERCENT_HIGH_VIX,
    }.get(vix_regime, config.TRAIL_PERCENT_MODERATE_VIX)


def _fg_normalize(score_0_100: float) -> float:
    """Fear & Greed 0-100 → contrarian 0-1 (pánico extremo es bullish)."""
    if score_0_100 <= 25:
        return 0.75   # Extreme Fear → contrarian bullish
    if score_0_100 <= 40:
        return 0.65   # Fear
    if score_0_100 <= 60:
        return 0.50   # Neutral
    if score_0_100 <= 75:
        return 0.35   # Greed → cautela
    return 0.20       # Extreme Greed → contrarian bearish


def run(symbol: str = "SPY") -> SpyCycleResult:
    """
    Ciclo completo SPY Specialist: investiga, puntúa, filtra y decide.
    Nunca lanza excepción — en caso de fallo parcial usa valores neutros.
    """
    logger.info(f"[SPY CYCLE] Iniciando investigacion 6-dimensiones para {symbol}")

    # ── 1. Macro ──────────────────────────────────────────────────────────────
    yield_curve_spread = None
    try:
        inflation  = get_inflation_data()
        employment = get_employment_data()
        rates      = get_rates_data()
        fed        = get_fed_watch_data()
        yield_curve_spread = rates.spread_10y2y
        ms = score_macro(
            inflation_score=inflation.score,
            employment_score=employment.score,
            rates_score=rates.score,
            fed_score=fed.score,
            yield_curve_spread=yield_curve_spread,
        )
    except Exception as exc:
        logger.error(f"[MACRO] Error: {exc}")
        ms = score_macro(0.5, 0.5, 0.5, 0.5)

    # ── 2. Eventos ────────────────────────────────────────────────────────────
    events_veto       = False
    events_reason     = ""
    events_multiplier = 1.0
    try:
        events   = get_upcoming_high_impact_events(hours_ahead=48)
        def_mode = get_defensive_mode(events)
        geo      = get_geopolitics_signal()
        events_veto       = def_mode["veto"]
        events_reason     = def_mode["reason"]
        events_multiplier = def_mode["score_multiplier"]
        es = score_events(
            score_multiplier=events_multiplier,
            veto=events_veto,
            geopolitics_score=geo.score,
            reason=events_reason,
        )
    except Exception as exc:
        logger.error(f"[EVENTS] Error: {exc}")
        es = score_events(score_multiplier=1.0, veto=False, geopolitics_score=0.5)

    # ── 3. Técnico ────────────────────────────────────────────────────────────
    rsi_veto    = False
    sma200_veto = False
    try:
        tech = get_multi_timeframe_analysis(symbol)
        rsi_veto    = tech.rsi_veto
        sma200_veto = tech.sma200_veto
        ts = score_technical(
            overall_score=tech.overall_score,
            bullish_count=tech.bullish_count,
            rsi_veto=rsi_veto,
            sma200_veto=sma200_veto,
            atr_veto=tech.atr_veto,
        )
    except Exception as exc:
        logger.error(f"[TECHNICAL] Error: {exc}")
        ts = score_technical(overall_score=0.5, bullish_count=1,
                             rsi_veto=False, sma200_veto=False, atr_veto=False)

    # ── 4. Componentes ────────────────────────────────────────────────────────
    earnings_veto = False
    try:
        holdings      = get_top_holdings_data()
        sectors       = get_sector_breadth()
        earnings      = get_earnings_data(hours_ahead=48)
        earnings_veto = earnings.veto_active
        cs = score_components(
            top10_score=holdings.score,
            sector_score=sectors.score,
            earnings_veto=earnings_veto,
        )
    except Exception as exc:
        logger.error(f"[COMPONENTS] Error: {exc}")
        cs = score_components(top10_score=0.5, sector_score=0.5, earnings_veto=False)

    # ── 5. Cross-assets ───────────────────────────────────────────────────────
    try:
        cross = get_cross_asset_data(spy_change_5d=None)
        xas   = score_cross_asset(
            cross_asset_score=cross.score,
            divergences=cross.divergences,
        )
    except Exception as exc:
        logger.error(f"[CROSS-ASSETS] Error: {exc}")
        xas = score_cross_asset(cross_asset_score=0.5, divergences=[])

    # ── 6. Sentimiento ────────────────────────────────────────────────────────
    vix_regime = "moderate"
    vix_value  = 20.0
    try:
        macro_ctx = get_macro_context()
        vix_term  = get_vix_term_structure()
        put_call  = get_put_call_ratio()
        headlines = fetch_headlines(symbol)
        vader     = analyze_sentiment(headlines)

        vix_regime         = macro_ctx.vix_regime
        vix_value          = macro_ctx.vix
        fg_normalized      = _fg_normalize(macro_ctx.fear_greed_score)
        vader_normalized   = (vader.compound + 1) / 2

        senti = score_sentiment(
            fear_greed_score=fg_normalized,
            vix_term_score=vix_term.score,
            put_call_score=put_call.score,
            news_sentiment_score=vader_normalized,
        )
    except Exception as exc:
        logger.error(f"[SENTIMENT] Error: {exc}")
        senti = score_sentiment(0.5, 0.5, 0.5, 0.5)

    # ── Pipeline de filtros ───────────────────────────────────────────────────
    trail_pct  = _trail_for_regime(vix_regime)
    dim_scores = DimensionScores(
        macro=ms.total,
        components=cs.total,
        sentiment=senti.total,
        technical=ts.total,
        events=es.total,
        cross_asset=xas.total,
    )

    filter_result = filter_evaluate(
        scores=dim_scores,
        vix_regime=vix_regime,
        events_veto=events_veto,
        events_reason=events_reason,
        events_multiplier=events_multiplier,
        earnings_veto=earnings_veto,
        rsi_veto=rsi_veto,
        sma200_veto=sma200_veto,
        macro_veto=ms.veto,
        trail_percent=trail_pct,
    )

    # ── Motor Claude ──────────────────────────────────────────────────────────
    snapshot = {
        "VIX spot":        f"{vix_value:.1f}",
        "VIX regime":      vix_regime,
        "Trail stop":      f"{trail_pct:.1f}%",
        "Macro":           f"{ms.total:.3f} ({ms.label})",
        "Technical":       f"{ts.total:.3f} ({ts.label})",
        "Components":      f"{cs.total:.3f} ({cs.label})",
        "Sentiment":       f"{senti.total:.3f} ({senti.label})",
        "Events":          f"{es.total:.3f}",
        "Cross-assets":    f"{xas.total:.3f} ({xas.label})",
        "Dimensions passing": f"{filter_result.dimensions_passing}/6",
    }
    claude: ClaudeAnalysis = claude_analyze(filter_result, snapshot)

    # ── Resolución final ──────────────────────────────────────────────────────
    # Si el filtro aprobó pero Claude rechaza → respetar veto de Claude
    final_decision = filter_result.decision
    final_size     = filter_result.size
    final_trail    = trail_pct

    if filter_result.approved and claude.decision == "NO_SIGNAL":
        final_decision = "NO_SIGNAL"
        final_size     = 0.0
        logger.warning("Claude rechazó señal aprobada por filtro — NO_SIGNAL final")
    elif final_decision == "APPROVE" and claude.size > 0:
        final_size  = claude.size
        final_trail = claude.trail_percent

    final_action = "buy" if final_decision == "APPROVE" else "none"

    logger.info(
        f"[SPY CYCLE] {final_decision} | conf={filter_result.total_score:.3f} "
        f"size={final_size:.0%} trail={final_trail}% | "
        f"macro={ms.total:.2f} tech={ts.total:.2f} comp={cs.total:.2f} "
        f"senti={senti.total:.2f} events={es.total:.2f} cross={xas.total:.2f}"
    )

    return SpyCycleResult(
        decision=final_decision,
        action=final_action,
        confidence=filter_result.total_score,
        size=final_size,
        trail_percent=final_trail,
        reason=filter_result.reason,
        claude_reasoning=claude.reasoning,
        symbol=symbol,
        vix_regime=vix_regime,
        vix_value=vix_value,
        filter_result=filter_result,
        dimension_scores=dim_scores,
    )
