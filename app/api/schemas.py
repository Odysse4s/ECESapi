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
