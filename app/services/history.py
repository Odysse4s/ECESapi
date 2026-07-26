"""In-memory execution history store with TTL eviction and capacity capping."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """In-memory representation of an execution record."""

    id: str
    language: str
    code_preview: str  # first 100 chars of code
    status: str | None  # None while pending
    created_at: datetime
    completed_at: datetime | None
    request: dict[str, Any]  # full serialized ExecutionRequest
    response: dict[str, Any] | None  # full serialized ExecutionResponse, None while pending


class ExecutionHistory:
    """Thread-safe in-memory execution history store with TTL and capacity limits."""

    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600) -> None:
        """Initialize the execution history store.

        Args:
            max_entries: Maximum number of execution records to retain.
            ttl_seconds: Time-to-live in seconds before an execution record expires.
        """
        self._max_entries: int = max(1, max_entries)
        self._ttl_seconds: int = max(1, ttl_seconds)
        self._records: dict[str, ExecutionRecord] = {}
        self._lock: threading.Lock = threading.Lock()

    def _evict(self) -> None:
        """Evict expired records based on TTL and oldest records when over capacity.

        Must be called while holding self._lock.
        """
        now = datetime.now(UTC)

        # 1. Evict expired entries
        expired_keys = [
            execution_id
            for execution_id, record in self._records.items()
            if (now - record.created_at).total_seconds() > self._ttl_seconds
        ]
        for execution_id in expired_keys:
            del self._records[execution_id]

        # 2. Evict oldest entries if capacity exceeded
        while len(self._records) > self._max_entries:
            oldest_key = next(iter(self._records))
            del self._records[oldest_key]

    def create(
        self,
        execution_id: str,
        request_dict: dict[str, Any],
        language: str,
        code: str,
    ) -> ExecutionRecord:
        """Create and store a new pending execution record.

        Args:
            execution_id: Unique identifier for the execution.
            request_dict: Full serialized ExecutionRequest dictionary.
            language: Programming language identifier.
            code: Source code string.

        Returns:
            The created ExecutionRecord instance.
        """
        code_preview = code[:100]
        now = datetime.now(UTC)
        record = ExecutionRecord(
            id=execution_id,
            language=language,
            code_preview=code_preview,
            status=None,
            created_at=now,
            completed_at=None,
            request=request_dict,
            response=None,
        )

        with self._lock:
            self._records[execution_id] = record
            self._evict()

        return record

    def complete(self, execution_id: str, response_dict: dict[str, Any]) -> None:
        """Update an existing execution record with completion response details.

        Args:
            execution_id: Unique identifier for the execution.
            response_dict: Full serialized ExecutionResponse dictionary.
        """
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                logger.warning(
                    "Attempted to complete unknown or expired execution record: %s",
                    execution_id,
                )
                return

            record.response = response_dict
            raw_status = response_dict.get("status")
            if hasattr(raw_status, "value"):
                record.status = str(raw_status.value)
            elif raw_status is not None:
                record.status = str(raw_status)
            else:
                record.status = None
            record.completed_at = datetime.now(UTC)

    def get(self, execution_id: str) -> ExecutionRecord | None:
        """Retrieve an execution record by ID if present and not expired.

        Args:
            execution_id: Unique identifier of the execution record.

        Returns:
            The ExecutionRecord if found and valid, otherwise None.
        """
        with self._lock:
            record = self._records.get(execution_id)
            if record is None:
                return None

            now = datetime.now(UTC)
            if (now - record.created_at).total_seconds() > self._ttl_seconds:
                del self._records[execution_id]
                return None

            return record

    def list_recent(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ExecutionRecord], int]:
        """Return recent execution records ordered newest first, plus total count.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            Tuple of (list of ExecutionRecord, total_active_record_count).
        """
        with self._lock:
            self._evict()
            all_records = list(reversed(self._records.values()))
            total_count = len(all_records)
            paginated = all_records[offset : offset + limit]
            return paginated, total_count

    def delete(self, execution_id: str) -> bool:
        """Delete an execution record from storage.

        Args:
            execution_id: Unique identifier of the execution record to remove.

        Returns:
            True if the record was found and deleted, False otherwise.
        """
        with self._lock:
            if execution_id in self._records:
                del self._records[execution_id]
                return True
            return False


history = ExecutionHistory(
    max_entries=settings.history_max_entries,
    ttl_seconds=settings.history_ttl_seconds,
)
