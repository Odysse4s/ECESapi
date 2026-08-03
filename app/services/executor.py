"""High-level execution orchestrator.

Bridges the FastAPI async world and the synchronous Docker runner by
dispatching container work onto a thread pool with concurrency throttling,
execution tracking, and metrics collection.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from app.api.schemas import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatus,
    Language,
)
from app.core import metrics
from app.core.config import settings
from app.core.metrics import ACTIVE_CONTAINERS
from app.services.concurrency import ConcurrencyExhaustedError, limiter
from app.services.history import history
from app.services.runner_docker import ContainerResult, run_container

logger = logging.getLogger(__name__)


def _classify_status(
    result: ContainerResult,
    language: Language,
) -> ExecutionStatus:
    """Map raw container metrics to a human-friendly status enum."""
    if result.timed_out:
        return ExecutionStatus.TIMEOUT

    if result.oom_killed:
        return ExecutionStatus.MEMORY_LIMIT_EXCEEDED

    # For compiled languages, the wrapper script exits with a sentinel code
    # when the compiler itself fails.
    if (
        language == Language.C
        and result.exit_code == settings.compile_error_exit_code
    ):
        return ExecutionStatus.COMPILATION_ERROR

    if result.exit_code != 0:
        return ExecutionStatus.RUNTIME_ERROR

    return ExecutionStatus.SUCCESS


async def execute(request: ExecutionRequest) -> ExecutionResponse:
    """Run *request* inside an ephemeral container and return the result.

    The heavy Docker interaction runs in ``asyncio.to_thread`` guarded by the
    concurrency limiter, so this coroutine never blocks the event loop.

    Args:
        request: Validated execution request containing code, language, and limits.

    Returns:
        ExecutionResponse: Outcome, output, resource metrics, and unique execution ID.

    Raises:
        ConcurrencyExhaustedError: When maximum concurrent executions are reached.
    """
    execution_id = str(uuid.uuid4())
    lang_str = (
        request.language.value
        if isinstance(request.language, Language)
        else str(request.language)
    )

    if settings.history_enabled:
        history.create(
            execution_id=execution_id,
            request_dict=request.model_dump(),
            language=lang_str,
            code=request.code,
        )

    try:
        async with limiter.throttle():
            ACTIVE_CONTAINERS.inc()
            try:
                result: ContainerResult = await asyncio.to_thread(
                    run_container,
                    execution_id=execution_id,
                    language=request.language,
                    code=request.code,
                    stdin_data=request.stdin,
                    timeout_seconds=request.timeout_seconds,
                    memory_limit_mb=request.memory_limit_mb,
                )
            finally:
                ACTIVE_CONTAINERS.dec()
    except ConcurrencyExhaustedError:
        logger.warning(
            "Concurrency limit exhausted for execution id=%s language=%s",
            execution_id,
            lang_str,
        )
        raise

    status = _classify_status(result, request.language)
    status_str = status.value if isinstance(status, ExecutionStatus) else str(status)
    peak_mb = round(result.peak_memory_bytes / (1024 * 1024), 2)
    execution_time_ms = round(result.wall_time_s * 1000, 2)

    logger.info(
        "Execution complete: execution_id=%s language=%s status=%s duration=%.4fs exit_code=%d",
        execution_id,
        lang_str,
        status_str,
        result.wall_time_s,
        result.exit_code,
    )

    metrics.record_execution(
        language=lang_str,
        status=status_str,
        duration_seconds=result.wall_time_s,
    )

    response = ExecutionResponse(
        execution_id=execution_id,
        status=status,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        execution_time_ms=execution_time_ms,
        peak_memory_mb=peak_mb,
        timed_out=result.timed_out,
        stdout_truncated=result.stdout_truncated,
        stderr_truncated=result.stderr_truncated,
    )

    if settings.history_enabled:
        history.complete(
            execution_id=execution_id,
            response_dict=response.model_dump(),
        )

    return response
