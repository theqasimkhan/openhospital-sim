"""
Structured logging configuration.

In development  → human-readable console output via structlog.
In production   → JSON lines emitted to stdout, consumed by log aggregators.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from app.core.config import settings


def _drop_color_message_key(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    """Remove uvicorn's `color_message` duplicate key before serialising."""
    event_dict.pop("color_message", None)
    return event_dict


def _add_app_context(
    _logger: WrappedLogger, _method: str, event_dict: EventDict
) -> EventDict:
    event_dict.setdefault("app", settings.APP_NAME)
    event_dict.setdefault("env", settings.APP_ENV)
    return event_dict


def configure_logging() -> None:
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _drop_color_message_key,
        _add_app_context,
    ]

    if settings.LOG_JSON:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        lvl = logging.WARNING if not settings.DEBUG else log_level
        logging.getLogger(noisy).setLevel(lvl)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
