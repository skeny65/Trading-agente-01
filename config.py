import os
from dotenv import load_dotenv

load_dotenv()

# ── NewsAPI ───────────────────────────────────────────────────────────────────
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

# ── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_URL: str    = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/webhook/bot2")

# ── Telegram (opcional) ───────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Watchlist ─────────────────────────────────────────────────────────────────
WATCHLIST: list[str] = [
    s.strip().upper()
    for s in os.getenv("WATCHLIST", "SPY,QQQ,IWM,DIA,XLK,XLF,XLE,XLV").split(",")
    if s.strip()
]

# ── Ciclo (en minutos) ────────────────────────────────────────────────────────
CYCLE_INTERVAL_MINUTES: int = int(os.getenv("CYCLE_INTERVAL_MINUTES", "60"))

# ── Umbrales de decisión ──────────────────────────────────────────────────────
MIN_CONFIDENCE: float   = float(os.getenv("MIN_CONFIDENCE", "0.70"))
CONSENSUS_REQUIRED: int = int(os.getenv("CONSENSUS_REQUIRED", "3"))
COOLDOWN_HOURS: int     = int(os.getenv("COOLDOWN_HOURS", "24"))

# ── Ventanas de datos ─────────────────────────────────────────────────────────
NEWS_LOOKBACK_HOURS: int = int(os.getenv("NEWS_LOOKBACK_HOURS", "4"))
PRICE_HISTORY_DAYS: int  = int(os.getenv("PRICE_HISTORY_DAYS", "60"))

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

# ── Position sizing conservador ───────────────────────────────────────────────
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
    if missing:
        raise EnvironmentError(
            f"Variables de entorno faltantes en .env: {', '.join(missing)}"
        )
