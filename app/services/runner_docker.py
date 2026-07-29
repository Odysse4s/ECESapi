"""Low-level Docker container lifecycle management for sandbox execution.

Responsibilities:
  - Build the shell command that decodes base64 code/stdin, compiles (if
    needed), and runs the user programme.
  - Create, start, wait-on, and clean up ephemeral containers.
  - Stream container memory stats in the background to capture peak RSS.
  - Enforce output size limits with truncation markers.
"""

from __future__ import annotations

import base64
import contextlib
import logging
import textwrap
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import docker
import docker.errors
import docker.models.containers
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import ReadTimeout

from app.api.schemas import Language
from app.core.config import settings
from app.core.exceptions import (
    ContainerCreationError,
    DockerUnavailableError,
)

logger = logging.getLogger(__name__)

# Truncation marker appended when output exceeds configured maximum bytes.
_TRUNCATION_MARKER = "\n--- [output truncated at 1 MiB] ---\n"


# ── Result dataclass ────────────────────────────────────────────────────────

@dataclass(slots=True)
class ContainerResult:
    """Raw results collected from a finished (or killed) container."""

    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    wall_time_s: float = 0.0
    peak_memory_bytes: int = 0
    timed_out: bool = False
    oom_killed: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


# ── Command builders per language ────────────────────────────────────────────

def _python_command() -> list[str]:
    """Build the shell execution command for Python code."""
    return [
        "sh", "-c",
        textwrap.dedent("""\
            echo "$CODE" | base64 -d > /tmp/main.py
            echo "$STDIN_DATA" | base64 -d | python -u /tmp/main.py
        """),
    ]


def _c_command() -> list[str]:
    """Build the shell compilation and execution command for C code."""
    # Uses sentinel exit code to flag compilation failure.
    return [
        "sh", "-c",
        textwrap.dedent("""\
            echo "$CODE" | base64 -d > /tmp/main.c
            COMP_ERR=$(gcc /tmp/main.c -o /tmp/main -lm 2>&1)
            if [ $? -ne 0 ]; then
                printf '%s' "$COMP_ERR" >&2
                exit {ce}
            fi
            echo "$STDIN_DATA" | base64 -d | /tmp/main
        """).format(ce=settings.compile_error_exit_code),
    ]


def _javascript_command() -> list[str]:
    """Build the shell execution command for Node.js JavaScript code."""
    return [
        "sh", "-c",
        textwrap.dedent("""\
            echo "$CODE" | base64 -d > /tmp/main.js
            echo "$STDIN_DATA" | base64 -d | node /tmp/main.js
        """),
    ]


_COMMAND_MAP: dict[Language, Callable[[], list[str]]] = {
    Language.PYTHON: _python_command,
    Language.C: _c_command,
    Language.JAVASCRIPT: _javascript_command,
}

_IMAGE_MAP: dict[Language, str] = {
    Language.PYTHON: settings.image_python,
    Language.C: settings.image_c,
    Language.JAVASCRIPT: settings.image_javascript,
}


def _get_image(language: Language) -> str:
    """Resolve the Docker image for the requested language.

    Args:
        language: Language enum value.

    Returns:
        str: Docker image name or tag.
    """
    mapping = {
        Language.PYTHON: settings.image_python,
        Language.C: settings.image_c,
        Language.JAVASCRIPT: settings.image_javascript,
    }
    return mapping.get(language, _IMAGE_MAP.get(language, settings.image_python))


# ── Memory-stats background monitor ─────────────────────────────────────────

@dataclass
class _MemoryMonitor:
    """Streams ``container.stats()`` on a daemon thread and records peak RSS."""

    container: docker.models.containers.Container | Any
    peak_bytes: int = 0
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = field(default=None, init=False)

    def start(self) -> None:
        """Start the background statistics polling thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the monitor thread to stop and wait for termination."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)

    # ── internal ──

    def _run(self) -> None:
        try:
            for chunk in self.container.stats(stream=True, decode=True):
                if self._stop.is_set():
                    break
                mem_stats = chunk.get("memory_stats", {})
                usage = mem_stats.get("usage", 0)
                # Some cgroup v1 hosts report ``max_usage``; prefer that.
                max_usage = mem_stats.get("max_usage", usage)
                self.peak_bytes = max(self.peak_bytes, usage, max_usage)
        except Exception:
            # Container removed / stream closed — totally expected.
            pass


# ── Public runner ────────────────────────────────────────────────────────────

def get_docker_client() -> docker.DockerClient:
    """Return a Docker client, raising a clear error if the daemon is unreachable.

    Returns:
        docker.DockerClient: Connected Docker client instance.

    Raises:
        DockerUnavailableError: When the Docker daemon cannot be reached.
    """
    try:
        client = docker.from_env()
        client.ping()
        return client
    except (docker.errors.DockerException, ReqConnectionError) as exc:
        raise DockerUnavailableError(
            f"Cannot reach Docker Engine: {exc}"
        ) from exc


def run_container(
    *,
    execution_id: str,
    language: Language,
    code: str,
    stdin_data: str,
    timeout_seconds: float,
    memory_limit_mb: int,
) -> ContainerResult:
    """Create, run, and clean up an ephemeral sandbox container.

    This function is synchronous and expected to be dispatched onto a
    thread pool by the async executor layer.

    Args:
        execution_id: Unique identifier for the execution request.
        language: Programming language of the snippet to execute.
        code: Source code string to execute inside the sandbox.
        stdin_data: Standard input stream content to feed the program.
        timeout_seconds: Hard wall-clock execution limit in seconds.
        memory_limit_mb: Memory ceiling in megabytes.

    Returns:
        ContainerResult: Raw execution output, exit code, and resource metrics.

    Raises:
        ContainerCreationError: If the Docker container cannot be created or image is missing.
        DockerUnavailableError: If the Docker daemon is unreachable.
    """
    client = get_docker_client()
    container: docker.models.containers.Container | Any = None
    monitor: _MemoryMonitor | None = None

    code_b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    stdin_b64 = base64.b64encode(stdin_data.encode("utf-8")).decode("ascii")
    image = _get_image(language)
    command = _COMMAND_MAP[language]()

    container_name = f"eces-{execution_id[:12]}"
    language_label = language.value if isinstance(language, Language) else str(language)
    labels = {
        "eces.execution_id": execution_id,
        "eces.language": language_label,
        "eces.created_by": "eces-api",
    }

    try:
        container = client.containers.create(
            image=image,
            name=container_name,
            command=command,
            environment={"CODE": code_b64, "STDIN_DATA": stdin_b64},
            labels=labels,
            # ── Security constraints ────────────────────────────────────
            network_mode="none",
            user=settings.container_user,
            read_only=True,
            security_opt=["no-new-privileges:true"],
            cap_drop=["ALL"],
            tmpfs={"/tmp": f"size={settings.tmpfs_size_mb}m,exec"},
            mem_limit=f"{memory_limit_mb}m",
            memswap_limit=f"{memory_limit_mb}m",  # disable swap
            nano_cpus=settings.container_nano_cpus,
            pids_limit=settings.container_pids_limit,  # mitigate fork bombs
            # NOTE: auto_remove is *not* set so we can inspect logs/state
            #       before explicit removal in the ``finally`` block.
        )
    except docker.errors.ImageNotFound as exc:
        raise ContainerCreationError(
            f"Docker image {image!r} not found locally. "
            f"Run `docker pull {image}` first."
        ) from exc
    except docker.errors.APIError as exc:
        raise ContainerCreationError(str(exc)) from exc

    try:
        t0 = time.perf_counter()
        container.start()

        # Start background memory monitor.
        monitor = _MemoryMonitor(container=container)
        monitor.start()

        # Wait for the container to finish (or timeout).
        timed_out = False
        try:
            result = container.wait(timeout=timeout_seconds)
            exit_code = result.get("StatusCode", -1)
        except (ReadTimeout, ReqConnectionError):
            timed_out = True
            exit_code = -1
            with contextlib.suppress(docker.errors.APIError):
                container.kill()

        wall_time = time.perf_counter() - t0
        monitor.stop()

        # Collect stdout / stderr.
        try:
            stdout_raw: bytes = container.logs(stdout=True, stderr=False)
            stderr_raw: bytes = container.logs(stdout=False, stderr=True)
        except docker.errors.APIError:
            stdout_raw = stderr_raw = b""

        # Enforce output byte limit with truncation markers.
        stdout_truncated = False
        if len(stdout_raw) > settings.max_output_bytes:
            stdout_truncated = True
            stdout = (
                stdout_raw[:settings.max_output_bytes].decode("utf-8", errors="replace")
                + _TRUNCATION_MARKER
            )
        else:
            stdout = stdout_raw.decode("utf-8", errors="replace")

        stderr_truncated = False
        if len(stderr_raw) > settings.max_output_bytes:
            stderr_truncated = True
            stderr = (
                stderr_raw[:settings.max_output_bytes].decode("utf-8", errors="replace")
                + _TRUNCATION_MARKER
            )
        else:
            stderr = stderr_raw.decode("utf-8", errors="replace")

        # Inspect OOM-kill flag.
        oom_killed = False
        try:
            state = client.api.inspect_container(container.id).get("State", {})
            oom_killed = state.get("OOMKilled", False)
        except docker.errors.APIError:
            pass

        return ContainerResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            wall_time_s=wall_time,
            peak_memory_bytes=monitor.peak_bytes,
            timed_out=timed_out,
            oom_killed=oom_killed,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )

    finally:
        if monitor is not None:
            monitor.stop()
        if container is not None:
            try:
                container.stop(timeout=1)
            except (docker.errors.APIError, Exception) as exc:
                logger.debug(
                    "Graceful stop skipped or failed for container %s: %s",
                    getattr(container, "short_id", "unknown"),
                    exc,
                )
            try:
                container.remove(force=True)
            except docker.errors.APIError:
                logger.warning(
                    "Failed to remove container %s",
                    getattr(container, "short_id", "unknown"),
                )
            except Exception as exc:
                logger.warning(
                    "Unexpected error removing container %s: %s",
                    getattr(container, "short_id", "unknown"),
                    exc,
                )
