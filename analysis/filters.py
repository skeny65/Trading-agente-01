"""
Sistema de filtros en cascada para el SPY Specialist.

PASO 1 — Filtros duros (vetos): cualquier veto → NO_SIGNAL inmediato.
PASO 2 — Score compuesto de las 6 dimensiones.
PASO 3 — Filtros suaves (modificadores de score).
PASO 4 — Validación final: score >= umbral + N dimensiones > 0.55.

El agente NO busca cuándo entrar — busca cuándo NO es seguro entrar.
"""
import logging
from dataclasses import dataclass, field

import config

logger = logging.getLogger(__name__)


@dataclass
class DimensionScores:
    macro: float       # 0.0–1.0
    components: float
    sentiment: float
    technical: float
    events: float
    cross_asset: float


@dataclass
class FilterResult:
    approved: bool
    decision: str          # "APPROVE" | "NO_SIGNAL"
    reason: str
    total_score: float
    size: float            # 0.0 si NO_SIGNAL
    score_multiplier: float = 1.0
    veto_triggers: list[str] = field(default_factory=list)
    dimension_scores: DimensionScores | None = None
    dimensions_passing: int = 0   # cuántas dimensiones > 0.55


# ── PASO 1: Filtros duros ─────────────────────────────────────────────────────

def check_hard_vetos(
    vix_regime: str,
    events_veto: bool,
    events_reason: str,
    earnings_veto: bool,
    rsi_veto: bool,
    sma200_veto: bool,
    macro_veto: bool,
) -> list[str]:
    """Retorna lista de vetos activos. Lista vacía = sin vetos."""
    vetos: list[str] = []
    if config.BLOCK_NEW_ON_EXTREME_VIX and vix_regime == "extreme":
        vetos.append(f"VIX extremo (>{30}) — mercado en pánico")
    if events_veto:
        vetos.append(events_reason)
    if earnings_veto:
        vetos.append(f"Earnings ≥{config.EARNINGS_TOP10_THRESHOLD} top-10 en 48h")
    if rsi_veto:
        vetos.append("RSI diario > 75 (sobrecompra extrema)")
    if sma200_veto:
        vetos.append("Precio < SMA200 diaria (modo defensivo)")
    if macro_veto:
        vetos.append("Curva invertida + macro deteriorada")
    return vetos


# ── PASO 2: Score compuesto ───────────────────────────────────────────────────

def compute_total_score(scores: DimensionScores) -> float:
    total = (
        scores.macro       * config.WEIGHT_MACRO
        + scores.components  * config.WEIGHT_COMPONENTS
        + scores.sentiment   * config.WEIGHT_SENTIMENT
        + scores.technical   * config.WEIGHT_TECHNICAL
        + scores.events      * config.WEIGHT_EVENTS
        + scores.cross_asset * config.WEIGHT_CROSS_ASSET
    )
    return round(max(0.0, min(1.0, total)), 4)


# ── PASO 3: Filtros suaves ────────────────────────────────────────────────────

def apply_soft_filters(
    total_score: float,
    score_multiplier: float,
    vix_regime: str,
    trail_percent: float,
) -> tuple[float, float]:
    """
    Retorna (adjusted_score, adjusted_trail_percent).
    Evento de impacto alto → score × 0.85, trail más ajustado.
    """
    adjusted_score = round(total_score * score_multiplier, 4)
    adjusted_trail = trail_percent
    if score_multiplier < 1.0:
        adjusted_trail = round(trail_percent * 0.70, 2)  # trail más ajustado
    return adjusted_score, adjusted_trail


# ── PASO 4: Validación final ──────────────────────────────────────────────────

def _count_passing_dimensions(scores: DimensionScores, threshold: float = 0.55) -> int:
    return sum([
        scores.macro       >= threshold,
        scores.components  >= threshold,
        scores.sentiment   >= threshold,
        scores.technical   >= threshold,
        scores.events      >= threshold,
        scores.cross_asset >= threshold,
    ])


def _get_size(score: float) -> float:
    if score >= 0.90:
        return config.SIZE_TIER_1
    if score >= 0.82:
        return config.SIZE_TIER_2
    if score >= 0.75:
        return config.SIZE_TIER_3
    return config.SIZE_TIER_4


# ── Función principal ─────────────────────────────────────────────────────────

def evaluate(
    scores: DimensionScores,
    vix_regime: str,
    events_veto: bool,
    events_reason: str,
    events_multiplier: float,
    earnings_veto: bool,
    rsi_veto: bool,
    sma200_veto: bool,
    macro_veto: bool,
    trail_percent: float,
) -> FilterResult:
    """
    Pipeline completo de filtros.
    Retorna FilterResult con approved=True solo si todos los pasos pasan.
    """

    # PASO 1: Vetos duros
    veto_triggers = check_hard_vetos(
        vix_regime=vix_regime,
        events_veto=events_veto,
        events_reason=events_reason,
        earnings_veto=earnings_veto,
        rsi_veto=rsi_veto,
        sma200_veto=sma200_veto,
        macro_veto=macro_veto,
    )
    if veto_triggers:
        reason = " | ".join(veto_triggers)
        logger.warning(f"VETO DURO: {reason}")
        return FilterResult(
            approved=False, decision="NO_SIGNAL",
            reason=reason, total_score=0.0, size=0.0,
            veto_triggers=veto_triggers, dimension_scores=scores,
        )

    # PASO 2: Score compuesto
    raw_score = compute_total_score(scores)

    # PASO 3: Filtros suaves
    adjusted_score, adjusted_trail = apply_soft_filters(
        raw_score, events_multiplier, vix_regime, trail_percent
    )

    # PASO 4: Validación final
    dimensions_passing = _count_passing_dimensions(scores)

    if adjusted_score < config.MIN_CONFIDENCE:
        reason = (
            f"Score {adjusted_score:.3f} < umbral {config.MIN_CONFIDENCE}"
            + (f" (multiplicador {events_multiplier:.2f} aplicado)" if events_multiplier < 1.0 else "")
        )
        logger.info(f"NO_SIGNAL: {reason}")
        return FilterResult(
            approved=False, decision="NO_SIGNAL",
            reason=reason, total_score=adjusted_score, size=0.0,
            score_multiplier=events_multiplier, dimension_scores=scores,
            dimensions_passing=dimensions_passing,
        )

    if dimensions_passing < config.MIN_DIMENSIONS_PASSING:
        reason = (
            f"Solo {dimensions_passing}/{config.MIN_DIMENSIONS_PASSING} "
            f"dimensiones > 0.55 (se requieren {config.MIN_DIMENSIONS_PASSING})"
        )
        logger.info(f"NO_SIGNAL: {reason}")
        return FilterResult(
            approved=False, decision="NO_SIGNAL",
            reason=reason, total_score=adjusted_score, size=0.0,
            score_multiplier=events_multiplier, dimension_scores=scores,
            dimensions_passing=dimensions_passing,
        )

    size = _get_size(adjusted_score)
    reason = (
        f"Score {adjusted_score:.3f} | {dimensions_passing}/6 dimensiones > 0.55 "
        f"| size={size:.0%} | trail={adjusted_trail}%"
    )
    logger.info(f"APPROVE SPY: {reason}")

    return FilterResult(
        approved=True, decision="APPROVE",
        reason=reason, total_score=adjusted_score, size=size,
        score_multiplier=events_multiplier,
        veto_triggers=[],
        dimension_scores=scores,
        dimensions_passing=dimensions_passing,
    )
