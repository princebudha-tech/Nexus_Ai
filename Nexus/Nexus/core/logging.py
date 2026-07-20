"""Structured logging with JSON lines and console output."""
from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STANDARD_LOG_RECORD_FIELDS = frozenset(
    logging.LogRecord(name="", level=0, pathname="", lineno=0, msg="", args=(), exc_info=None).__dict__.keys()
) | {"message", "asctime"}

_CONFIGURED = False
_VALID_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _resolve_level(level_name: str) -> int:
    normalized = level_name.strip().upper()
    if normalized not in _VALID_LEVELS:
        raise ValueError(f"Invalid log level {level_name!r}. Must be one of: {', '.join(sorted(_VALID_LEVELS))}")
    return getattr(logging, normalized)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        extras = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_LOG_RECORD_FIELDS}
        if extras:
            payload["extra"] = _json_safe(extras)
        return json.dumps(payload, default=str, ensure_ascii=False)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


class HumanReadableFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%H:%M:%S")


def configure_logging(
    *,
    log_level: str = "INFO",
    log_dir: str | Path = "./data/logs",
    log_filename: str = "nexus.jsonl",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    enable_console: bool = True,
) -> None:
    """Configure root logger for NEXUS. Idempotent."""
    global _CONFIGURED
    root_logger = logging.getLogger("nexus")
    root_logger.setLevel(_resolve_level(log_level))

    # Remove old handlers to avoid duplication
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # JSON file handler (rotating)
    log_path = Path(log_dir) / log_filename
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)

    # Console handler (human-readable)
    if enable_console:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(HumanReadableFormatter())
        root_logger.addHandler(console)

    root_logger.propagate = False
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger under the 'nexus' namespace."""
    if not _CONFIGURED:
        # Minimal default config for tests
        configure_logging(log_level="INFO", enable_console=True)
    return logging.getLogger(f"nexus.{name}")