"""
Application logging configuration for SURAKSHA Smart PPE.

Keeps logging configuration in one place so individual modules only need:

    logger = logging.getLogger(__name__)
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "suraksha.log"

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """
    Configure application-wide logging.

    Logs are written to:
        server/logs/suraksha.log

    and also displayed in the terminal.
    """

    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers when uvicorn --reload
    # or application startup initializes logging more than once.
    if getattr(root_logger, "_suraksha_configured", False):
        return

    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )

    # Console logging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Rotating file logging
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    root_logger._suraksha_configured = True

    root_logger.info(
        "SURAKSHA logging initialized | log_file=%s",
        LOG_FILE,
    )

