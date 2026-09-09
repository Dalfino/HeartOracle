"""JSON line logger (PRD-002 §11).

Schema: {"ts": iso, "level", "component", "study_token"?, "event", "duration_ms"?, "extra": {}}
One logger per component; no PHI fields ever.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "taskName",
    "message", "asctime", "component", "study_token", "event", "duration_ms",
}


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line, PRD §11 schema."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        extra: dict[str, Any] = {
            k: v for k, v in record.__dict__.items() if k not in _RESERVED and not k.startswith("_")
        }
        payload: dict[str, Any] = {
            "ts": ts,
            "level": record.levelname,
            "component": getattr(record, "component", record.name),
            "event": getattr(record, "event", record.getMessage()),
            "extra": extra,
        }
        study_token = getattr(record, "study_token", None)
        if study_token is not None:
            payload["study_token"] = study_token
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        return json.dumps(payload, default=str)


def get_logger(component: str, level: str | None = None) -> logging.Logger:
    """Return a component logger emitting JSON lines to stderr."""
    logger = logging.getLogger(f"oracle.{component}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False
    if level is not None:
        logger.setLevel(level.upper())
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    study_token: str | None = None,
    duration_ms: float | None = None,
    **extra: Any,
) -> None:
    """Log a single structured event."""
    logger.log(
        level,
        event,
        extra={
            "component": logger.name.removeprefix("oracle."),
            "event": event,
            "study_token": study_token,
            "duration_ms": duration_ms,
            **extra,
        },
    )
