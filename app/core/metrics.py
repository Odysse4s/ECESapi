"""Prometheus operational metrics for the ECES sandbox platform."""

from __future__ import annotations

import logging
from typing import Any

from prometheus_client import Counter, Gauge, Histogram, generate_latest

logger = logging.getLogger(__name__)

EXECUTIONS_TOTAL = Counter(
    "eces_executions_total",
    "Total executions",
    ["language", "status"],
)

EXECUTION_DURATION = Histogram(
    "eces_execution_duration_seconds",
    "Execution duration",
    ["language"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

ACTIVE_CONTAINERS = Gauge(
    "eces_active_containers",
    "Currently running sandbox containers",
)

RATE_LIMIT_HITS = Counter(
    "eces_rate_limit_hits_total",
    "Rate limit rejections",
)


def record_execution(
    language: Any,
    status: Any,
    duration_seconds: float,
) -> None:
    """Record execution completion and latency metrics.

    Args:
        language: Programming language string or enum.
        status: Execution status string or enum.
        duration_seconds: Execution wall-clock duration in seconds.
    """
    lang_str = str(language.value if hasattr(language, "value") else language)
    status_str = str(status.value if hasattr(status, "value") else status)

    EXECUTIONS_TOTAL.labels(language=lang_str, status=status_str).inc()
    EXECUTION_DURATION.labels(language=lang_str).observe(duration_seconds)


def get_metrics_text() -> str:
    """Generate and return current Prometheus metrics as a UTF-8 text string.

    Returns:
        Formatted metrics ready to be served over HTTP.
    """
    return generate_latest().decode("utf-8")
