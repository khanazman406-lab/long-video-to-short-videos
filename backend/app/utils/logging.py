"""Structured logging with job/video context. Never logs secrets."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a single structured event line. Drops any secret-looking keys."""
    redacted = {"api_key", "apikey", "secret", "token", "password", "access_key", "secret_key"}
    safe = {k: v for k, v in fields.items() if k.lower() not in redacted}
    logger.info("%s %s", event, json.dumps(safe, default=str))
