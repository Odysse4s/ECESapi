from __future__ import annotations
from enum import Enum

class Language(str, Enum):
    PYTHON = "python"
    C = "c"
    JAVASCRIPT = "javascript"

class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    MEMORY_LIMIT_EXCEEDED = "memory_limit_exceeded"
    RUNTIME_ERROR = "runtime_error"
    COMPILATION_ERROR = "compilation_error"

from pydantic import BaseModel, Field
from app.core.config import settings

class ExecutionRequest(BaseModel):
    language: Language
    code: str = Field(..., min_length=1, max_length=settings.max_code_size_bytes)
    stdin: str = Field(default="", max_length=settings.max_code_size_bytes)
    timeout_seconds: float = Field(default=settings.default_timeout_seconds, gt=0, le=settings.max_timeout_seconds)
    memory_limit_mb: int = Field(default=settings.default_memory_limit_mb, ge=4, le=settings.max_memory_limit_mb)

class ExecutionResponse(BaseModel):
    status: ExecutionStatus
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float
    peak_memory_mb: float = 0.0
    timed_out: bool = False
