from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ghosty_input.config import app_data_dir

LOGGER_NAME = "ghosty_input"


def log_dir() -> Path:
    return app_data_dir() / "logs"


def log_path() -> Path:
    return log_dir() / "ghosty-input.log"


def configure_logging(*, level: int = logging.INFO) -> Path:
    """Configure a small persistent runtime log for alpha diagnostics.

    The application never logs camera frames or typed content. The log is for
    startup, shutdown, device/backend failures, and crash tracebacks only.
    """

    target = log_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    target_resolved = target.resolve()
    for handler in logger.handlers:
        base = getattr(handler, "baseFilename", None)
        if base and Path(base).resolve() == target_resolved:
            return target

    handler = RotatingFileHandler(
        target,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.info("runtime logging initialized")
    return target


def get_logger(name: str | None = None) -> logging.Logger:
    suffix = f".{name}" if name else ""
    return logging.getLogger(f"{LOGGER_NAME}{suffix}")
