"""One log file per pipeline run, in addition to the existing stderr progress
lines -- so a failure (rate limit, bad extraction, whatever) can be diagnosed
after the fact instead of only being visible while the run is live in a terminal.
"""

import logging
import time
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"


def get_logger(name: str) -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    log_path = LOGS_DIR / f"{name}_{time.strftime('%Y%m%d_%H%M%S')}.log"

    logger = logging.getLogger(f"agent.{name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(stream_handler)

    logger.info("Log file: %s", log_path)
    return logger
