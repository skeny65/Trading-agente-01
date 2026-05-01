"""
Motor de decisión final SPY via Claude API.

Recibe los resultados del filtro cascada + snapshot de mercado,
llama a Claude con el system prompt cacheado y devuelve una
decisión estructurada. Fallback a NO_SIGNAL en caso de error.
"""
import json
import logging
from dataclasses import dataclass

import anthropic

import config
from analysis.filters import DimensionScores, FilterResult

logger = logging.getLogger(__name__)

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


# System prompt estable — se cachea en el primer request, ahorrando tokens.
_SYSTEM_PROMPT = """You are a quantitative SPY swing-trading analyst. Evaluate structured market data across 6 research dimensions and decide whether to initiate a long SPY position.

## Strategy: SPY Specialist — Swing Trading
- Asset: SPY (S&P 500 ETF), NYSE, USD
- Timeframe: swing trades, typically 3–15 days
- Direction: long only
- Mode: DRY_RUN (paper trading)

## 6 Dimensions and Weights
1. Macro (25%): FRED data — CPI, PCE, unemployment, jobless claims, Fed Funds Rate, yield curve
2. Technical (20%): multi-timeframe RSI/MACD/Bollinger Bands/SMA200 (1D, 4H, 1H)
3. Components (20%): SPY top-10 holdings breadth, 11 sector ETFs rotation
4. Sentiment (15%): VIX term structure (contango/backwardation), put/call ratio, news VADER
5. Events (10%): FOMC proximity, high-impact economic calendar, geopolitics
6. Cross-Assets (10%): DXY, TLT, HYG, QQQ divergences vs SPY

## Approval Gate
Approve only if ALL of the following:
- Total weighted score >= 0.72
- At least 5 of 6 dimensions have score > 0.55
- No hard veto is active

## Hard Vetos (automatic NO_SIGNAL)
- VIX > 30 (extreme panic)
- FOMC meeting within 24 hours
- 3 or more SPY top-10 earnings within 48 hours
- Daily RSI > 75 (extreme overbought)
- SPY price below SMA200 daily (bear regime)
- Yield curve deeply inverted AND macro deteriorating

## Position Sizing (fraction of portfolio)
- Score >= 0.90 → 25%
- Score >= 0.82 → 18%
- Score >= 0.75 → 12%
- Score >= 0.72 → 8%

## Trailing Stop by VIX Regime
- Low VIX (< 15): 3.0%
- Moderate VIX (15–25): 4.0%
- High VIX (25–30): 5.5%

## Output
Respond ONLY with a valid JSON object, no markdown, no extra text:
{
  "decision": "APPROVE" or "NO_SIGNAL",
  "action": "buy" or "none",
  "confidence": <float 0.0–1.0>,
  "size": <float, portfolio fraction, e.g. 0.18>,
  "trail_percent": <float, e.g. 4.0>,
  "reasoning": "<2–3 sentences explaining the key factors>"
}"""


@dataclass
class ClaudeAnalysis:
    decision: str       # "APPROVE" | "NO_SIGNAL"
    action: str         # "buy" | "none"
    confidence: float
    size: float
    trail_percent: float
    reasoning: str


def _fallback(reason: str) -> ClaudeAnalysis:
    return ClaudeAnalysis(
        decision="NO_SIGNAL",
        action="none",
        confidence=0.0,
        size=0.0,
        trail_percent=4.0,
        reasoning=reason,
    )


def analyze(
    filter_result: FilterResult,
    market_snapshot: dict,
) -> ClaudeAnalysis:
    """
    Llama a Claude API con los datos de mercado estructurados.
    Retorna ClaudeAnalysis; en cualquier error devuelve NO_SIGNAL fallback.

    Args:
        filter_result: resultado del pipeline de filtros cascada
        market_snapshot: dict con datos adicionales de mercado (precio, VIX, etc.)
    """
    try:
        user_content = _build_user_prompt(filter_result, market_snapshot)
        client = _get_client()

        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_content}],
        )

        raw = response.content[0].text.strip()

        # Limpiar bloques markdown si Claude los incluye
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        result = ClaudeAnalysis(
            decision=str(data.get("decision", "NO_SIGNAL")),
            action=str(data.get("action", "none")),
            confidence=float(data.get("confidence", 0.0)),
            size=float(data.get("size", 0.0)),
            trail_percent=float(data.get("trail_percent", 4.0)),
            reasoning=str(data.get("reasoning", "")),
        )

        usage = response.usage
        cache_read = getattr(usage, "cache_read_input_tokens", 0)
        cache_create = getattr(usage, "cache_creation_input_tokens", 0)
        logger.info(
            f"Claude: decision={result.decision} confidence={result.confidence:.2f} "
            f"size={result.size:.0%} | tokens in={usage.input_tokens} "
            f"out={usage.output_tokens} cache_read={cache_read} cache_create={cache_create}"
        )
        return result

    except json.JSONDecodeError as exc:
        logger.error(f"Claude returned invalid JSON: {exc}")
        return _fallback(f"JSON parse error: {exc}")
    except anthropic.APIError as exc:
        logger.error(f"Claude API error: {exc}")
        return _fallback(f"Claude API error: {exc}")
    except Exception as exc:
        logger.error(f"Claude analyst unexpected error: {exc}")
        return _fallback(f"Unexpected error: {exc}")


def _build_user_prompt(filter_result: FilterResult, snapshot: dict) -> str:
    scores = filter_result.dimension_scores

    lines = [
        "## SPY Market Analysis — Current Cycle",
        "",
        f"Filter decision:     {filter_result.decision}",
        f"Total score:         {filter_result.total_score:.4f}",
        f"Dimensions passing:  {filter_result.dimensions_passing}/6 (threshold > 0.55)",
        f"Score multiplier:    {filter_result.score_multiplier:.2f}",
        f"Veto triggers:       {', '.join(filter_result.veto_triggers) if filter_result.veto_triggers else 'none'}",
        f"Filter reason:       {filter_result.reason}",
        "",
        "### Dimension Scores (0.0–1.0, higher = more bullish)",
    ]

    if scores:
        lines += [
            f"  Macro:         {scores.macro:.4f}  (weight 25%)",
            f"  Technical:     {scores.technical:.4f}  (weight 20%)",
            f"  Components:    {scores.components:.4f}  (weight 20%)",
            f"  Sentiment:     {scores.sentiment:.4f}  (weight 15%)",
            f"  Events:        {scores.events:.4f}  (weight 10%)",
            f"  Cross-Assets:  {scores.cross_asset:.4f}  (weight 10%)",
        ]

    if snapshot:
        lines += ["", "### Market Snapshot"]
        for key, val in snapshot.items():
            lines.append(f"  {key}: {val}")

    lines += [
        "",
        "Provide your trading decision as a JSON object following the output format in your instructions.",
    ]

    return "\n".join(lines)
