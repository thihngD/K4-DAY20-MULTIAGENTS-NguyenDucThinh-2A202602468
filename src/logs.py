"""Ghi log cho từng agent: mỗi agent một tệp trong `logs/`, communication.log ghi JSON từng dòng."""
import logging
import os
from pathlib import Path

LOG_DIR = Path(os.getenv("RQ2_LOG_DIR", Path(__file__).resolve().parents[1] / "logs"))
_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Trả về logger ghi vào `logs/<name>.log` (một handler duy nhất cho mỗi tên)."""
    logger = logging.getLogger(f"rq2.{name}")
    if not logger.handlers:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(LOG_DIR / f"{name}.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
