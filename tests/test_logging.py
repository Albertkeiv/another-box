from __future__ import annotations

import logging

from another_box.logging_config import (
    LOGGER_NAME,
    compact_exception,
    configure_logging,
    install_exception_hook,
    read_application_log,
)


def test_application_log_is_written_and_read(tmp_path):
    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    for handler in original_handlers:
        logger.removeHandler(handler)
    log_path = tmp_path / "logs" / "application.log"
    try:
        configured = configure_logging(log_path)
        configured.error("test application error")
        for handler in configured.handlers:
            handler.flush()

        text = read_application_log(log_path)

        assert "Another Box started" in text
        assert "test application error" in text
    finally:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        for handler in original_handlers:
            logger.addHandler(handler)


def test_compact_exception_contains_only_type_and_message():
    error = ValueError("invalid profile")

    text = compact_exception(error)

    assert text == "ValueError: invalid profile"
    assert "Traceback" not in text


def test_exception_hook_writes_no_traceback(tmp_path, monkeypatch):
    logger = logging.getLogger(LOGGER_NAME)
    original_handlers = list(logger.handlers)
    for handler in original_handlers:
        logger.removeHandler(handler)
    log_path = tmp_path / "logs" / "application.log"
    original_hook = __import__("sys").excepthook
    try:
        configured = configure_logging(log_path)
        install_exception_hook()
        error = RuntimeError("startup failed")
        __import__("sys").excepthook(RuntimeError, error, error.__traceback__)
        for handler in configured.handlers:
            handler.flush()

        text = read_application_log(log_path)

        assert "RuntimeError: startup failed" in text
        assert "Traceback" not in text
    finally:
        __import__("sys").excepthook = original_hook
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)
        for handler in original_handlers:
            logger.addHandler(handler)
