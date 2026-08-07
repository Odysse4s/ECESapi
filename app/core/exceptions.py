"""Custom exception hierarchy for the sandbox execution pipeline."""

from __future__ import annotations


class SandboxError(Exception):
    """Base class for all sandbox-related errors."""


class UnsupportedLanguageError(SandboxError):
    """Raised when the requested language is not supported."""

    def __init__(self, language: str) -> None:
        self.language = language
        super().__init__(f"Unsupported language: {language!r}")


class CodeTooLargeError(SandboxError):
    """Raised when the submitted code exceeds the size limit."""

    def __init__(self, size: int, limit: int) -> None:
        self.size = size
        self.limit = limit
        super().__init__(
            f"Code payload is {size} bytes which exceeds the {limit}-byte limit"
        )


class DockerUnavailableError(SandboxError):
    """Raised when Docker Engine cannot be reached."""


class ExecutionTimeoutError(SandboxError):
    """Raised when container execution exceeds the allowed timeout."""


class ContainerCreationError(SandboxError):
    """Raised when the Docker container cannot be created."""


class ConcurrencyExhaustedError(SandboxError):
    """Raised when the maximum number of concurrent executions is reached."""
