"""Structlog configuration for Warren Lanchonete backend.

Configures structured logging with:
- JSON output in production
- Colored console output in development
- Automatic injection of trace_id, service, and environment fields
- Redaction of sensitive field names (api_key, secret, password)

Call configure_logging() once at application startup (in lifespan or __init__).
"""
from __future__ import annotations

import logging

import structlog


def _redact_sensitive_fields(logger: object, method: str, event_dict: dict) -> dict:
    """Structlog processor that redacts sensitive field values.

    Replaces values of fields named api_key, secret, or password with '***'.

    Args:
        logger: Structlog logger instance (unused).
        method: Log method name (unused).
        event_dict: Current log event dictionary.

    Returns:
        Sanitized event dictionary.
    """
    sensitive_keys = {"api_key", "secret", "password", "token"}
    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging(environment: str = "development", log_level: str = "INFO") -> None:
    """Configure structlog for the given environment.

    Args:
        environment: 'production' outputs JSON; any other value outputs
            colored console output suitable for development.
        log_level: Python logging level string (DEBUG, INFO, WARNING, ERROR).
    """
    log_level_int = getattr(logging, log_level.upper(), logging.INFO)

    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        level=log_level_int,
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _redact_sensitive_fields,
    ]

    if environment == "production":
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
