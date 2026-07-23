"""Sliding-window rate limiting middleware for API routes."""

from __future__ import annotations

import collections
import logging
import math
import threading
import time
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings

if TYPE_CHECKING:
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter middleware for API routes.

    Tracks request timestamps per client IP in memory using double-ended queues.
    Rejects requests exceeding the configured threshold with a 429 status code
    and an RFC-compliant ``Retry-After`` header.
    """

    def __init__(
        self,
        app: ASGIApp,
        enabled: bool | None = None,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        """Initialize the rate limiting middleware.

        Args:
            app: The ASGI application instance.
            enabled: Override for settings.rate_limit_enabled if provided.
            max_requests: Override for settings.rate_limit_requests if provided.
            window_seconds: Override for settings.rate_limit_window_seconds if provided.
        """
        super().__init__(app)
        self.enabled: bool = enabled if enabled is not None else settings.rate_limit_enabled
        self.max_requests: int = (
            max_requests if max_requests is not None else settings.rate_limit_requests
        )
        self.window_seconds: int = (
            window_seconds if window_seconds is not None else settings.rate_limit_window_seconds
        )
        self._clients: dict[str, collections.deque[float]] = {}
        self._lock: threading.Lock = threading.Lock()
        self._last_cleanup: float = time.monotonic()
        self._cleanup_interval_seconds: float = 60.0

    def _extract_client_ip(self, request: Request) -> str:
        """Resolve client IP address from proxy headers or connection host.

        Args:
            request: The incoming HTTP request.

        Returns:
            Extracted IP address string.
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    def _cleanup_stale_entries(self, now: float) -> None:
        """Evict timestamp queues that have no activity inside the active window.

        Args:
            now: Current monotonic timestamp.
        """
        cutoff = now - self.window_seconds
        stale_ips: list[str] = []

        for ip, timestamps in self._clients.items():
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                stale_ips.append(ip)

        for ip in stale_ips:
            del self._clients[ip]

        self._last_cleanup = now
        logger.debug(
            "Cleaned up rate limit entries; removed %d stale IP buckets",
            len(stale_ips),
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Evaluate rate limit rules and forward or reject the request.

        Args:
            request: The incoming HTTP request.
            call_next: Next request processing callable in the ASGI chain.

        Returns:
            HTTP response from the downstream application or 429 Too Many Requests.
        """
        if not self.enabled or not request.url.path.startswith("/api/"):
            return await call_next(request)

        client_ip = self._extract_client_ip(request)
        now = time.monotonic()

        with self._lock:
            if now - self._last_cleanup >= self._cleanup_interval_seconds:
                self._cleanup_stale_entries(now)

            cutoff = now - self.window_seconds
            timestamps = self._clients.setdefault(client_ip, collections.deque())

            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.max_requests:
                oldest_timestamp = timestamps[0]
                retry_after_seconds = max(
                    1,
                    math.ceil(oldest_timestamp + self.window_seconds - now),
                )
                logger.warning(
                    "Rate limit exceeded for %s: %d requests in %ds window (retry in %ds)",
                    client_ip,
                    len(timestamps),
                    self.window_seconds,
                    retry_after_seconds,
                )
                try:
                    from app.core.metrics import RATE_LIMIT_HITS

                    RATE_LIMIT_HITS.inc()
                except Exception:
                    pass

                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": (
                            f"Too many requests. Limit is {self.max_requests} "
                            f"requests per {self.window_seconds} seconds."
                        )
                    },
                    headers={"Retry-After": str(retry_after_seconds)},
                )

            timestamps.append(now)

        return await call_next(request)
