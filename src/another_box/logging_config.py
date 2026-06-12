from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

LOGGER_NAME = "another_box"


def compact_exception(error: BaseException) -> str:
    name = type(error).__name__
    message = str(error).strip()
    return f"{name}: {message}" if message else name


def configure_logging(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            return logger

    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.info("Another Box started")
    return logger


def install_exception_hook() -> None:
    logger = logging.getLogger(LOGGER_NAME)
    original_hook = sys.excepthook

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            original_hook(exception_type, exception, traceback)
            return
        logger.critical("Unhandled exception: %s", compact_exception(exception))

    sys.excepthook = handle_exception


def read_application_log(log_path: Path) -> str:
    if not log_path.is_file():
        return ""
    try:
        return log_path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        return f"Не удалось прочитать журнал приложения: {error}"
