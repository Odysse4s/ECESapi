"""API router for the ``/api/v1`` namespace."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.schemas import (
    ErrorResponse,
    ExecutionRequest,
    ExecutionResponse,
    HistoryDetailResponse,
    HistoryEntry,
    HistoryListResponse,
    Language,
    LanguageInfo,
    LanguageListResponse,
)
from app.core.config import settings
from app.core.exceptions import (
    ContainerCreationError,
    DockerUnavailableError,
    SandboxError,
)
from app.services import executor
from app.services.concurrency import ConcurrencyExhaustedError
from app.services.history import history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# ── Static Language Registry ─────────────────────────────────────────────────

LANGUAGE_REGISTRY: dict[str, dict[str, Any]] = {
    Language.PYTHON.value: {
        "name": Language.PYTHON.value,
        "display_name": "Python 3.12",
        "image": settings.image_python,
        "compiled": False,
        "file_extension": ".py",
    },
    Language.C.value: {
        "name": Language.C.value,
        "display_name": "C (GCC 14)",
        "image": settings.image_c,
        "compiled": True,
        "file_extension": ".c",
    },
    Language.JAVASCRIPT.value: {
        "name": Language.JAVASCRIPT.value,
        "display_name": "JavaScript (Node.js 22)",
        "image": settings.image_javascript,
        "compiled": False,
        "file_extension": ".js",
    },
}


def _format_datetime(dt: Any) -> str | None:
    """Format a datetime object or string to an ISO 8601 string representation.

    Args:
        dt: The datetime object, string, or None.

    Returns:
        ISO 8601 string or None if input was None.
    """
    if dt is None:
        return None
    if hasattr(dt, "isoformat"):
        return str(dt.isoformat())
    return str(dt)


# ── Execution Endpoints ──────────────────────────────────────────────────────


@router.post(
    "/execute",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute a code snippet in an ephemeral sandbox",
    tags=["execution"],
    responses={
        200: {
            "model": ExecutionResponse,
            "description": "Code execution result and resource usage metrics",
        },
        422: {
            "model": ErrorResponse,
            "description": "Validation error (invalid request payload)",
        },
        429: {
            "model": ErrorResponse,
            "description": "Server is at capacity (concurrency limit reached)",
        },
        500: {
            "model": ErrorResponse,
            "description": "Internal sandbox error",
        },
        503: {
            "model": ErrorResponse,
            "description": "Docker Engine unavailable",
        },
    },
)
async def execute_code(payload: ExecutionRequest) -> ExecutionResponse:
    """Accept an untrusted code snippet, execute it inside an isolated container,
    and return execution metrics.

    Args:
        payload: Code execution parameters including language, code, stdin, and limits.

    Returns:
        ExecutionResponse containing execution status, output, exit code, and runtime stats.

    Raises:
        HTTPException: 429 when concurrency limit is saturated,
                       503 when Docker daemon cannot be reached,
                       500 when container creation or execution fails unexpectedly.
    """
    try:
        return await executor.execute(payload)
    except ConcurrencyExhaustedError as exc:
        logger.warning("Concurrency limit exhausted: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Server is at capacity. Try again later.",
        ) from exc
    except DockerUnavailableError as exc:
        logger.error("Docker unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Docker Engine is not reachable. Please check the server configuration.",
        ) from exc
    except ContainerCreationError as exc:
        logger.error("Container creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create sandbox container: {exc}",
        ) from exc
    except SandboxError as exc:
        logger.exception("Unexpected sandbox error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


# ── Language Metadata Endpoints ──────────────────────────────────────────────


@router.get(
    "/languages",
    response_model=LanguageListResponse,
    status_code=status.HTTP_200_OK,
    summary="List supported programming languages",
    tags=["languages"],
    responses={
        200: {
            "model": LanguageListResponse,
            "description": "List of supported execution languages with metadata",
        },
    },
)
async def list_languages() -> LanguageListResponse:
    """Return metadata for all programming languages supported by the sandbox.

    Returns:
        LanguageListResponse containing available languages, compiler flags, and Docker images.
    """
    languages = [
        LanguageInfo(
            name=str(info["name"]),
            display_name=str(info["display_name"]),
            image=getattr(settings, f"image_{info['name']}", str(info["image"])),
            compiled=bool(info["compiled"]),
            file_extension=str(info["file_extension"]),
        )
        for info in LANGUAGE_REGISTRY.values()
    ]
    return LanguageListResponse(languages=languages)


# ── Execution History Endpoints ──────────────────────────────────────────────


@router.get(
    "/executions",
    response_model=HistoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List recent executions",
    tags=["history"],
    responses={
        200: {
            "model": HistoryListResponse,
            "description": "Paginated collection of past execution records",
        },
        404: {
            "model": ErrorResponse,
            "description": "Execution history is disabled",
        },
    },
)
async def list_executions(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of records to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of records to skip for pagination",
    ),
) -> HistoryListResponse:
    """List recent execution records with pagination.

    Args:
        limit: Number of records to return (1-100, default 20).
        offset: Number of records to skip from the beginning (default 0).

    Returns:
        HistoryListResponse with execution summaries and total active count.

    Raises:
        HTTPException: 404 if execution history is disabled in settings.
    """
    if not settings.history_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution history is disabled.",
        )

    records, total = history.list_recent(limit=limit, offset=offset)
    executions = [
        HistoryEntry(
            id=rec.id,
            language=rec.language,
            code_preview=rec.code_preview,
            status=rec.status,
            created_at=_format_datetime(rec.created_at) or "",
            completed_at=_format_datetime(rec.completed_at),
        )
        for rec in records
    ]
    return HistoryListResponse(
        executions=executions,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/executions/{execution_id}",
    response_model=HistoryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get full execution details",
    tags=["history"],
    responses={
        200: {
            "model": HistoryDetailResponse,
            "description": "Full execution record including request and response details",
        },
        404: {
            "model": ErrorResponse,
            "description": "Execution record not found or history disabled",
        },
    },
)
async def get_execution(
    execution_id: str = Path(..., description="Unique execution identifier"),
) -> HistoryDetailResponse:
    """Retrieve full details of a specific execution run by ID.

    Args:
        execution_id: Unique identifier of the execution record.

    Returns:
        HistoryDetailResponse containing metadata, request payload, and response metrics.

    Raises:
        HTTPException: 404 if history is disabled or the execution record does not exist.
    """
    if not settings.history_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution history is disabled.",
        )

    record = history.get(execution_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution record '{execution_id}' not found.",
        )

    return HistoryDetailResponse(
        id=record.id,
        language=record.language,
        code_preview=record.code_preview,
        status=record.status,
        created_at=_format_datetime(record.created_at) or "",
        completed_at=_format_datetime(record.completed_at),
        request=record.request,
        response=record.response,
    )


@router.delete(
    "/executions/{execution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an execution record",
    tags=["history"],
    responses={
        204: {
            "description": "Execution record successfully deleted",
        },
        404: {
            "model": ErrorResponse,
            "description": "Execution record not found or history disabled",
        },
    },
)
async def delete_execution(
    execution_id: str = Path(..., description="Unique execution identifier"),
) -> None:
    """Delete an execution record from history by ID.

    Args:
        execution_id: Unique identifier of the execution record to delete.

    Raises:
        HTTPException: 404 if history is disabled or the execution record does not exist.
    """
    if not settings.history_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution history is disabled.",
        )

    deleted = history.delete(execution_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution record '{execution_id}' not found.",
        )
