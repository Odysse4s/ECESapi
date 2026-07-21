"""Concurrency limiter enforcing max simultaneous sandbox executions."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.exceptions import ConcurrencyExhaustedError

logger = logging.getLogger(__name__)


class ConcurrencyLimiter:
    """Asyncio semaphore-based concurrency limiter for sandbox workloads."""

    def __init__(self, max_concurrent: int) -> None:
        """Initialize the concurrency limiter.

        Args:
            max_concurrent: Maximum number of concurrent executions allowed.
        """
        self._max_concurrent: int = max(1, max_concurrent)
        self._semaphore: asyncio.Semaphore = asyncio.Semaphore(self._max_concurrent)
        self._active_count: int = 0

    @asynccontextmanager
    async def throttle(self) -> AsyncGenerator[None, None]:
        """Acquire a slot, yield, then release.

        Raises:
            ConcurrencyExhaustedError: If the semaphore cannot be acquired within 0.5s.

        Yields:
            None once an execution slot is secured.
        """
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=0.5)
        except TimeoutError as exc:
            logger.warning(
                "Concurrency capacity of %d exhausted (timeout after 0.5s)",
                self._max_concurrent,
            )
            raise ConcurrencyExhaustedError(
                f"Concurrency limit of {self._max_concurrent} executions reached"
            ) from exc

        self._active_count += 1
        try:
            yield
        finally:
            self._active_count = max(0, self._active_count - 1)
            self._semaphore.release()

    @property
    def active_count(self) -> int:
        """Return the number of slots currently acquired."""
        return self._active_count

    @property
    def max_concurrent(self) -> int:
        """Return the maximum allowed concurrent executions."""
        return self._max_concurrent


limiter = ConcurrencyLimiter(settings.max_concurrent_executions)
