"""Pydantic v2 schemas for the ECES API endpoints."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings

# ── Enums ────────────────────────────────────────────────────────────────────


class Language(StrEnum):
    """Supported execution languages."""

    PYTHON = "python"
    C = "c"
    JAVASCRIPT = "javascript"


class ExecutionStatus(StrEnum):
    """Possible outcomes of a sandbox execution."""

    SUCCESS = "success"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"


# ── Request / Response Models ────────────────────────────────────────────────


class ExecutionRequest(BaseModel):
    """Payload sent by the client to run a code snippet."""

    language: Language = Field(
        ...,
        description="Programming language of the submitted code.",
        examples=["python"],
    )
    code: str = Field(
        ...,
        min_length=1,
        max_length=settings.max_code_size_bytes,
        description="Source code to execute.",
        examples=["print('Hello world!')"],
    )
    stdin: str = Field(
        default="",
        max_length=settings.max_code_size_bytes,
        description="Data piped to the process's standard input.",
    )
    timeout_seconds: float = Field(
        default=settings.default_timeout_seconds,
        gt=0,
        le=settings.max_timeout_seconds,
        description="Maximum wall-clock seconds before the execution is killed.",
    )
    memory_limit_mb: int = Field(
        default=settings.default_memory_limit_mb,
        ge=4,
        le=settings.max_memory_limit_mb,
        description="Hard memory ceiling in MiB enforced via cgroups.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "language": "python",
                    "code": "print('Hello world!')",
                    "stdin": "",
                    "timeout_seconds": 3.0,
                    "memory_limit_mb": 64,
                }
            ]
        }
    }


class ExecutionResponse(BaseModel):
    """Result returned after sandbox execution completes (or is terminated)."""

    execution_id: str = Field(
        ...,
        description="Unique identifier assigned to this execution run.",
    )
    status: ExecutionStatus = Field(
        ...,
        description="High-level outcome category.",
    )
    exit_code: int = Field(
        ...,
        description="Process exit code (-1 when killed by timeout or OOM).",
    )
    stdout: str = Field(
        default="",
        description="Captured standard output (truncated to max limit).",
    )
    stderr: str = Field(
        default="",
        description="Captured standard error (truncated to max limit).",
    )
    stdout_truncated: bool = Field(
        default=False,
        description="Whether stdout exceeded the output limit and was truncated.",
    )
    stderr_truncated: bool = Field(
        default=False,
        description="Whether stderr exceeded the output limit and was truncated.",
    )
    execution_time_ms: float = Field(
        ...,
        ge=0,
        description="Wall-clock execution time in milliseconds.",
    )
    peak_memory_mb: float = Field(
        default=0.0,
        ge=0,
        description="Peak resident-set size in MiB.",
    )
    timed_out: bool = Field(
        default=False,
        description="Whether the execution was killed by timeout.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "execution_id": "exec-abc12345",
                    "status": "success",
                    "exit_code": 0,
                    "stdout": "Hello world!\n",
                    "stderr": "",
                    "stdout_truncated": False,
                    "stderr_truncated": False,
                    "execution_time_ms": 142.5,
                    "peak_memory_mb": 14.8,
                    "timed_out": False,
                }
            ]
        }
    }


# ── Error Response ───────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    """Standardized error payload returned across API endpoints."""

    detail: str = Field(
        ...,
        description="Human-readable explanation of the error.",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional request correlation ID for tracing.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "detail": "Server is at capacity. Try again later.",
                    "request_id": "req-123456",
                }
            ]
        }
    }


# ── Language Models ──────────────────────────────────────────────────────────


class LanguageInfo(BaseModel):
    """Metadata describing a supported programming language."""

    name: str = Field(
        ...,
        description="Canonical language identifier (e.g., 'python').",
    )
    display_name: str = Field(
        ...,
        description="Human-readable display name (e.g., 'Python 3.12').",
    )
    image: str = Field(
        ...,
        description="Docker image tag used for executing snippets.",
    )
    compiled: bool = Field(
        ...,
        description="Whether the language requires ahead-of-time compilation.",
    )
    file_extension: str = Field(
        ...,
        description="Source code file extension including the dot (e.g., '.py').",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "python",
                    "display_name": "Python 3.12",
                    "image": "python:3.12-alpine",
                    "compiled": False,
                    "file_extension": ".py",
                }
            ]
        }
    }


class LanguageListResponse(BaseModel):
    """List of all languages supported by the sandbox."""

    languages: list[LanguageInfo] = Field(
        ...,
        description="Collection of supported language definitions.",
    )


# ── History Models ───────────────────────────────────────────────────────────


class HistoryEntry(BaseModel):
    """Summary of a past execution run."""

    id: str = Field(
        ...,
        description="Unique execution identifier.",
    )
    language: str = Field(
        ...,
        description="Programming language executed.",
    )
    code_preview: str = Field(
        ...,
        description="Truncated preview snippet of the executed code.",
    )
    status: str | None = Field(
        default=None,
        description="Outcome status if execution concluded, or None if pending.",
    )
    created_at: str = Field(
        ...,
        description="ISO 8601 formatted timestamp when execution was initiated.",
    )
    completed_at: str | None = Field(
        default=None,
        description="ISO 8601 formatted timestamp when execution finished.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "exec-abc12345",
                    "language": "python",
                    "code_preview": "print('Hello world!')",
                    "status": "success",
                    "created_at": "2026-10-13T12:00:00Z",
                    "completed_at": "2026-10-13T12:00:01Z",
                }
            ]
        }
    }


class HistoryListResponse(BaseModel):
    """Paginated collection of past execution runs."""

    executions: list[HistoryEntry] = Field(
        ...,
        description="List of execution summary entries.",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total count of execution records available in history.",
    )
    limit: int = Field(
        ...,
        ge=1,
        description="Page size limit applied to the query.",
    )
    offset: int = Field(
        ...,
        ge=0,
        description="Offset index applied to the query.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "executions": [
                        {
                            "id": "exec-abc12345",
                            "language": "python",
                            "code_preview": "print('Hello world!')",
                            "status": "success",
                            "created_at": "2026-10-13T12:00:00Z",
                            "completed_at": "2026-10-13T12:00:01Z",
                        }
                    ],
                    "total": 1,
                    "limit": 20,
                    "offset": 0,
                }
            ]
        }
    }


class HistoryDetailResponse(HistoryEntry):
    """Detailed record of a single execution run including request and response payloads."""

    request: dict[str, Any] = Field(
        ...,
        description="Original execution request payload as a dictionary.",
    )
    response: dict[str, Any] | None = Field(
        default=None,
        description="Execution response payload as a dictionary, or None if pending.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "exec-abc12345",
                    "language": "python",
                    "code_preview": "print('Hello world!')",
                    "status": "success",
                    "created_at": "2026-10-13T12:00:00Z",
                    "completed_at": "2026-10-13T12:00:01Z",
                    "request": {
                        "language": "python",
                        "code": "print('Hello world!')",
                        "stdin": "",
                        "timeout_seconds": 3.0,
                        "memory_limit_mb": 64,
                    },
                    "response": {
                        "execution_id": "exec-abc12345",
                        "status": "success",
                        "exit_code": 0,
                        "stdout": "Hello world!\n",
                        "stderr": "",
                        "stdout_truncated": False,
                        "stderr_truncated": False,
                        "execution_time_ms": 142.5,
                        "peak_memory_mb": 14.8,
                        "timed_out": False,
                    },
                }
            ]
        }
    }


# ── Health Model ─────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Service health and capacity status."""

    status: str = Field(
        ...,
        description="High-level health status ('ok' or 'degraded').",
    )
    version: str = Field(
        ...,
        description="Application version string.",
    )
    docker_connected: bool = Field(
        ...,
        description="Whether the Docker daemon is reachable.",
    )
    images_available: dict[str, bool] = Field(
        ...,
        description="Availability map of configured language Docker images.",
    )
    active_executions: int = Field(
        ...,
        ge=0,
        description="Number of currently executing sandbox containers.",
    )
    max_concurrent: int = Field(
        ...,
        ge=1,
        description="Maximum allowed concurrent executions.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "ok",
                    "version": "1.0.0",
                    "docker_connected": True,
                    "images_available": {
                        "python": True,
                        "c": True,
                        "javascript": True,
                    },
                    "active_executions": 2,
                    "max_concurrent": 10,
                }
            ]
        }
    }


# ── WebSocket Models ─────────────────────────────────────────────────────────


class WebSocketRequest(ExecutionRequest):
    """Execution request received via WebSocket push connection."""


class WebSocketResponse(BaseModel):
    """Message returned over WebSocket connection."""

    type: str = Field(
        ...,
        description="Outcome category: 'result' or 'error'.",
        examples=["result", "error"],
    )
    data: dict[str, Any] = Field(
        ...,
        description="Payload dictionary containing execution response or error detail.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "type": "result",
                    "data": {
                        "execution_id": "exec-abc12345",
                        "status": "success",
                        "exit_code": 0,
                        "stdout": "Hello world!\n",
                        "stderr": "",
                        "stdout_truncated": False,
                        "stderr_truncated": False,
                        "execution_time_ms": 142.5,
                        "peak_memory_mb": 14.8,
                        "timed_out": False,
                    },
                }
            ]
        }
    }
