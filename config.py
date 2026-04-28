import os
from dotenv import load_dotenv

load_dotenv()

# ── NewsAPI ───────────────────────────────────────────────────────────────────
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

# ── Webhook ───────────────────────────────────────────────────────────────────
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/webhook/bot2")

# ── Telegram (opcional) ───────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Watchlist ─────────────────────────────────────────────────────────────────
WATCHLIST: list[str] = [
    s.strip().upper()
    for s in os.getenv("WATCHLIST", "SPY,QQQ").split(",")
    if s.strip()
]

# ── Ciclo ─────────────────────────────────────────────────────────────────────
CYCLE_INTERVAL_HOURS: int = int(os.getenv("CYCLE_INTERVAL_HOURS", "4"))
MIN_CONFIDENCE: float = float(os.getenv("MIN_CONFIDENCE", "0.65"))
COOLDOWN_HOURS: int = int(os.getenv("COOLDOWN_HOURS", "4"))

# ── Riesgo por operación ──────────────────────────────────────────────────────
DEFAULT_STOP_LOSS: float   = float(os.getenv("DEFAULT_STOP_LOSS", "0.02"))
DEFAULT_TAKE_PROFIT: float = float(os.getenv("DEFAULT_TAKE_PROFIT", "0.04"))

# ── Modo ──────────────────────────────────────────────────────────────────────
DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"

# ── Horario de mercado (ET) ───────────────────────────────────────────────────
MARKET_OPEN_HOUR: int = 9
MARKET_OPEN_MINUTE: int = 30
MARKET_CLOSE_HOUR: int = 16
MARKET_TZ: str = "America/New_York"


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
