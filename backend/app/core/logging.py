"""Structured logging configuration."""

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Render application log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(log_level: str) -> None:
    """Configure the root logger once with a JSON stream handler."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    if any(getattr(handler, "_safescreen_handler", False) for handler in root_logger.handlers):
        return

    handler = logging.StreamHandler()
    handler._safescreen_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(JsonFormatter())
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
