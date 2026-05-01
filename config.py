import os
from dotenv import load_dotenv

load_dotenv()

# ── Símbolo primario (especialista SPY) ───────────────────────────────────────
SYMBOL: str = os.getenv("SYMBOL", "SPY")

# ── Watchlist legacy (multi-símbolo, se mantiene para compatibilidad) ─────────
WATCHLIST: list[str] = [
    s.strip().upper()
    for s in os.getenv("WATCHLIST", SYMBOL).split(",")
    if s.strip()
]

# ── NewsAPI ───────────────────────────────────────────────────────────────────
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

# ── FRED API (datos macroeconómicos oficiales US) ─────────────────────────────
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# ── Anthropic API (Claude — motor de análisis) ────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL: str      = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")
CLAUDE_MAX_TOKENS: int = int(os.getenv("CLAUDE_MAX_TOKENS", "800"))

# ── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_URL: str    = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/webhook/bot2")

# ── Telegram (opcional) ───────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Ciclo (en minutos) ────────────────────────────────────────────────────────
CYCLE_INTERVAL_MINUTES: int = int(os.getenv("CYCLE_INTERVAL_MINUTES", "60"))

# ── Pre-market briefing ───────────────────────────────────────────────────────
PRE_MARKET_BRIEFING_TIME_ET: str = os.getenv("PRE_MARKET_BRIEFING_TIME_ET", "07:00")

def _parse_priority_cycles(raw: str) -> list[tuple[int, int]]:
    result = []
    for token in raw.split(","):
        token = token.strip()
        if ":" in token:
            h, m = token.split(":")
            result.append((int(h), int(m)))
    return result

PRIORITY_CYCLES_ET: list[tuple[int, int]] = _parse_priority_cycles(
    os.getenv("PRIORITY_CYCLES_ET", "09:45,12:30,15:30")
)

# ── Umbrales de decisión ──────────────────────────────────────────────────────
MIN_CONFIDENCE: float         = float(os.getenv("MIN_CONFIDENCE",         "0.72"))
MIN_DIMENSIONS_PASSING: int   = int(os.getenv("MIN_DIMENSIONS_PASSING",   "5"))
CONSENSUS_REQUIRED: int       = int(os.getenv("CONSENSUS_REQUIRED",       "3"))
COOLDOWN_HOURS: int           = int(os.getenv("COOLDOWN_HOURS",           "24"))

# ── Ventanas de datos ─────────────────────────────────────────────────────────
NEWS_LOOKBACK_HOURS: int = int(os.getenv("NEWS_LOOKBACK_HOURS", "4"))
PRICE_HISTORY_DAYS: int  = int(os.getenv("PRICE_HISTORY_DAYS",  "60"))

# ── Pesos por dimensión (suma = 1.0) ──────────────────────────────────────────
WEIGHT_MACRO: float       = float(os.getenv("WEIGHT_MACRO",       "0.25"))
WEIGHT_COMPONENTS: float  = float(os.getenv("WEIGHT_COMPONENTS",  "0.20"))
WEIGHT_SENTIMENT: float   = float(os.getenv("WEIGHT_SENTIMENT",   "0.15"))
WEIGHT_TECHNICAL: float   = float(os.getenv("WEIGHT_TECHNICAL",   "0.20"))
WEIGHT_EVENTS: float      = float(os.getenv("WEIGHT_EVENTS",      "0.10"))
WEIGHT_CROSS_ASSET: float = float(os.getenv("WEIGHT_CROSS_ASSET", "0.10"))

# ── Trailing stop dinámico por régimen VIX ────────────────────────────────────
EXIT_STRATEGY: str = os.getenv("EXIT_STRATEGY", "trailing_stop")

TRAIL_PERCENT_LOW_VIX: float      = float(os.getenv("TRAIL_PERCENT_LOW_VIX",      "3.0"))
TRAIL_PERCENT_MODERATE_VIX: float = float(os.getenv("TRAIL_PERCENT_MODERATE_VIX", "4.0"))
TRAIL_PERCENT_HIGH_VIX: float     = float(os.getenv("TRAIL_PERCENT_HIGH_VIX",     "5.5"))
TAKE_PROFIT_HIGH_VIX: float       = float(os.getenv("TAKE_PROFIT_HIGH_VIX",       "8.0"))
BLOCK_NEW_ON_EXTREME_VIX: bool    = os.getenv("BLOCK_NEW_ON_EXTREME_VIX", "true").lower() == "true"

MAX_HOLDING_DAYS_LOW: int      = int(os.getenv("MAX_HOLDING_DAYS_LOW",      "15"))
MAX_HOLDING_DAYS_MODERATE: int = int(os.getenv("MAX_HOLDING_DAYS_MODERATE", "10"))
MAX_HOLDING_DAYS_HIGH: int     = int(os.getenv("MAX_HOLDING_DAYS_HIGH",     "7"))

# ── Eventos / modo defensivo ──────────────────────────────────────────────────
ECONOMIC_CALENDAR_SOURCE: str = os.getenv("ECONOMIC_CALENDAR_SOURCE", "investing")
FOMC_BLOCK_HOURS_BEFORE: int  = int(os.getenv("FOMC_BLOCK_HOURS_BEFORE", "24"))
FOMC_BLOCK_HOURS_AFTER: int   = int(os.getenv("FOMC_BLOCK_HOURS_AFTER",  "2"))
EARNINGS_TOP10_THRESHOLD: int = int(os.getenv("EARNINGS_TOP10_THRESHOLD", "3"))

# ── Position sizing — tiers por score (single-asset SPY) ─────────────────────
# score >= 0.90 → 25% | >= 0.82 → 18% | >= 0.75 → 12% | >= 0.72 → 8%
SIZE_TIER_1: float = float(os.getenv("SIZE_TIER_1", "0.25"))
SIZE_TIER_2: float = float(os.getenv("SIZE_TIER_2", "0.18"))
SIZE_TIER_3: float = float(os.getenv("SIZE_TIER_3", "0.12"))
SIZE_TIER_4: float = float(os.getenv("SIZE_TIER_4", "0.08"))

# ── Position sizing legacy (multi-símbolo, se mantiene para compatibilidad) ───
SIZE_HIGH_CONFIDENCE: float   = float(os.getenv("SIZE_HIGH_CONFIDENCE",   "0.08"))
SIZE_MEDIUM_CONFIDENCE: float = float(os.getenv("SIZE_MEDIUM_CONFIDENCE", "0.05"))
SIZE_LOW_CONFIDENCE: float    = float(os.getenv("SIZE_LOW_CONFIDENCE",    "0.03"))
MAX_CONCURRENT_POSITIONS: int = int(os.getenv("MAX_CONCURRENT_POSITIONS", "12"))
MAX_TOTAL_EXPOSURE: float     = float(os.getenv("MAX_TOTAL_EXPOSURE",     "0.80"))

# ── Modo de operación ─────────────────────────────────────────────────────────
DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"

# ── Horario de mercado (ET) ───────────────────────────────────────────────────
MARKET_OPEN_HOUR: int   = 9
MARKET_OPEN_MINUTE: int = 30
MARKET_CLOSE_HOUR: int  = 16
MARKET_TZ: str          = "America/New_York"


def validate() -> None:
    missing = []
    if not NEWSAPI_KEY:
        missing.append("NEWSAPI_KEY")
    if not WEBHOOK_SECRET:
        missing.append("WEBHOOK_SECRET")
    if not FRED_API_KEY:
        missing.append("FRED_API_KEY (obtener gratis en https://fred.stlouisfed.org/docs/api/api_key.html)")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY (obtener en https://console.anthropic.com)")
    if missing:
        raise EnvironmentError(
            f"Variables de entorno faltantes en .env: {', '.join(missing)}"
        )
