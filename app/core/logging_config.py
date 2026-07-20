"""Structured JSON and standard logging configuration."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.middleware.request_id import REQUEST_ID_CTX_VAR


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that emits log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the specified record into a JSON string.

        Args:
            record: The LogRecord instance to format.

        Returns:
            A single-line JSON string representing the structured log record.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": REQUEST_ID_CTX_VAR.get(""),
        }

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str)


def setup_logging(debug: bool = False, json_format: bool = True) -> None:
    """Configure the root logger with a StreamHandler and appropriate formatter.

    Args:
        debug: If True, set the root log level to DEBUG; otherwise INFO.
        json_format: If True, use JSONFormatter; otherwise use plain text formatting.
    """
    level = logging.DEBUG if debug else logging.INFO
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear pre-existing handlers to prevent duplicate lines
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
        )

    root_logger.addHandler(handler)
