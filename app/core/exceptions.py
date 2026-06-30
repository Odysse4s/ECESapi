class SandboxError(Exception):
    """Base class for all sandbox errors."""

class UnsupportedLanguageError(SandboxError):
    pass

class CodeTooLargeError(SandboxError):
    pass

class DockerUnavailableError(SandboxError):
    pass

class ExecutionTimeoutError(SandboxError):
    pass

class ContainerCreationError(SandboxError):
    pass
