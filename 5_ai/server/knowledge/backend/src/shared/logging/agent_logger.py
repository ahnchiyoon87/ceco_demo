"""Convenience helpers for structured deep-agent logging."""

from __future__ import annotations

from typing import Any

from .smart_logger import SmartLogger


def log_agent_event(
    level: str,
    message: str,
    *,
    category: str = "deep_agent",
    **params: Any,
) -> None:
    """Write a structured deep-agent log entry."""

    payload = {key: value for key, value in params.items() if value is not None}
    SmartLogger.log(
        level=level,
        message=message,
        category=category,
        params=payload or None,
    )
