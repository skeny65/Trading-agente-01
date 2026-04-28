"""
excel_logger.py — Registra cada analisis en logs/trade_log.xlsx.
Una fila por simbolo por ciclo, independientemente del resultado.
Si el archivo esta abierto en Excel, advierte sin crashear el agente.
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

EXCEL_FILE = Path(__file__).parent / "logs" / "trade_log.xlsx"

COLUMNS = [
    "timestamp_utc",
    "cycle_id",
    "mode",
    "priority_cycle",
    "symbol",
    "status",
    "decision",
    "action",
    "price",
    "change_pct",
    "sma20",
    "sma50",
    "trend_strength",
    "volume_ratio",
    "sentiment_compound",
    "sentiment_label",
    "fear_greed_score",
    "fear_greed_label",
    "vix",
    "vix_regime",
    "score_trend",
    "score_sentiment",
    "score_macro",
    "score_vix",
    "score_total",
    "confidence",
    "size",
    "trail_percent",
    "take_profit_pct",
    "max_holding_days",
    "reason",
    "webhook_status",
]


def append_excel_rows(rows: list[dict]) -> None:
    """Append a list of row dicts to trade_log.xlsx. Creates headers on first run."""
    if not rows:
        return

    try:
        import openpyxl
    except ImportError:
        logger.warning("openpyxl no instalado — ejecuta: pip install openpyxl")
        return

    EXCEL_FILE.parent.mkdir(parents=True, exist_ok=True)

    try:
        if EXCEL_FILE.exists():
            wb = openpyxl.load_workbook(EXCEL_FILE)
            ws = wb.active
        else:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Analisis"
            ws.append(COLUMNS)

        for row in rows:
            ws.append([row.get(col, "") for col in COLUMNS])

        wb.save(EXCEL_FILE)
        logger.info(f"trade_log.xlsx: +{len(rows)} fila(s) guardadas")

    except PermissionError:
        logger.warning(
            "trade_log.xlsx esta abierto en Excel — cierra el archivo para que los datos se guarden"
        )
    except Exception as exc:
        logger.error(f"Error al escribir trade_log.xlsx: {exc}")
