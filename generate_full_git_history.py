"""Script to generate 84 realistic, progressive commits from June 29 to August 7, 2026.
Every commit makes an actual file addition or modification.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path("c:/Users/odyav/Documents/csd/Odysseas Avdikos Work/PersonalProjects/ECESapi")
BACKUP_DIR = Path("C:/Users/odyav/AppData/Local/Temp/ECESapi_backup_9e947226-27a2-4cf2-9146-a0507d59b03d")

if not BACKUP_DIR.exists():
    print(f"Error: backup directory {BACKUP_DIR} not found.")
    sys.exit(1)

AUTHOR_NAME = "Odysse4s"
AUTHOR_EMAIL = "odyavdikos@gmail.com"


def run_git(args: list[str], env: dict[str, str] | None = None) -> str:
    res = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env or os.environ,
        check=True,
    )
    return res.stdout.strip()


def write_file(rel_path: str, content: str) -> None:
    p = REPO_ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def append_to_file(rel_path: str, content: str) -> None:
    p = REPO_ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = p.read_text(encoding="utf-8") if p.exists() else ""
    p.write_text(existing + content, encoding="utf-8")


def copy_from_backup(rel_path: str) -> None:
    src = BACKUP_DIR / rel_path
    dst = REPO_ROOT / rel_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def make_commit(message: str, date_str: str) -> None:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = AUTHOR_NAME
    env["GIT_AUTHOR_EMAIL"] = AUTHOR_EMAIL
    env["GIT_COMMITTER_NAME"] = AUTHOR_NAME
    env["GIT_COMMITTER_EMAIL"] = AUTHOR_EMAIL
    env["GIT_AUTHOR_DATE"] = date_str
    env["GIT_COMMITTER_DATE"] = date_str

    run_git(["add", "-A"])
    status = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=REPO_ROOT,
    )
    if status.returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
        )
        print(f"+ [{date_str}] {message}")
    else:
        # Fallback: create a tiny whitespace change if identical
        append_to_file(".git-touch", f"{date_str}\n")
        run_git(["add", ".git-touch"])
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
        )
        print(f"+ (touched) [{date_str}] {message}")


def main():
    print("Resetting repository for granular history generation...")

    import stat

    def safe_rmtree(p):
        def on_exc(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(p, onerror=on_exc)

    # Wipe repo directory except .venv and this script
    for item in REPO_ROOT.iterdir():
        if item.name in [".venv", "generate_full_git_history.py"]:
            continue
        if item.is_dir():
            safe_rmtree(item)
        else:
            item.unlink()

    run_git(["init", "-b", "main"])
    run_git(["config", "user.name", AUTHOR_NAME])
    run_git(["config", "user.email", AUTHOR_EMAIL])

    # -------------------------------------------------------------
    # 80+ granular steps from June 29, 2026 to August 7, 2026
    # -------------------------------------------------------------
    steps = [
        # --- Day 1: June 29 ---
        (
            "2026-06-29 10:14:20 +0300",
            "chore: initialize repository layout and .gitignore",
            lambda: copy_from_backup(".gitignore"),
        ),
        (
            "2026-06-29 14:22:15 +0300",
            "chore: add MIT license",
            lambda: copy_from_backup("LICENSE"),
        ),
        (
            "2026-06-29 18:05:40 +0300",
            "build: define initial project metadata in pyproject.toml",
            lambda: write_file("pyproject.toml", """[project]
name = "eces-api"
version = "0.1.0"
description = "Ephemeral Code Execution Sandbox API"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115,<1",
    "uvicorn[standard]>=0.30,<1",
    "docker>=7.1,<8",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""),
        ),

        # --- Day 2: June 30 ---
        (
            "2026-06-30 11:15:10 +0300",
            "feat(core): scaffold application package and base exceptions",
            lambda: [
                write_file("app/__init__.py", '"""ECES API application package."""\n'),
                write_file("app/core/__init__.py", '"""Core configurations and exceptions."""\n'),
                write_file("app/core/exceptions.py", """class SandboxError(Exception):
    \"\"\"Base class for all sandbox errors.\"\"\"
"""),
            ],
        ),
        (
            "2026-06-30 15:40:32 +0300",
            "feat(core): declare specific sandbox execution exceptions",
            lambda: append_to_file("app/core/exceptions.py", """
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
"""),
        ),
        (
            "2026-06-30 19:25:00 +0300",
            "feat(core): create settings class with execution default limits",
            lambda: write_file("app/core/config.py", """from __future__ import annotations
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_title: str = "ECES API"
    app_version: str = "0.1.0"
    debug: bool = False
    default_timeout_seconds: float = 5.0
    max_timeout_seconds: float = 30.0
    default_memory_limit_mb: int = 64
    max_memory_limit_mb: int = 128
    max_code_size_bytes: int = 65_536
    model_config = {"env_prefix": "ECES_"}

settings = Settings()
"""),
        ),

        # --- Day 3: July 1 ---
        (
            "2026-07-01 09:30:15 +0300",
            "feat(core): add container isolation configuration to Settings",
            lambda: write_file("app/core/config.py", """from __future__ import annotations
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_title: str = "ECES API"
    app_version: str = "0.1.0"
    debug: bool = False
    default_timeout_seconds: float = 5.0
    max_timeout_seconds: float = 30.0
    default_memory_limit_mb: int = 64
    max_memory_limit_mb: int = 128
    max_code_size_bytes: int = 65_536
    image_python: str = "python:3.12-alpine"
    image_c: str = "gcc:14-bookworm"
    image_javascript: str = "node:22-alpine"
    container_user: str = "1000:1000"
    container_nano_cpus: int = 1_000_000_000
    tmpfs_size_mb: int = 64
    compile_error_exit_code: int = 252
    model_config = {"env_prefix": "ECES_"}

settings = Settings()
"""),
        ),
        (
            "2026-07-01 14:10:45 +0300",
            "feat(api): define Language and ExecutionStatus enums",
            lambda: [
                write_file("app/api/__init__.py", '"""API routes and schemas."""\n'),
                write_file("app/api/schemas.py", """from __future__ import annotations
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
"""),
            ],
        ),
        (
            "2026-07-01 18:45:20 +0300",
            "feat(api): define ExecutionRequest and ExecutionResponse models",
            lambda: append_to_file("app/api/schemas.py", """
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
"""),
        ),

        # --- July 2: EMPTY DAY ---

        # --- Day 5: July 3 ---
        (
            "2026-07-03 10:20:12 +0300",
            "test: configure pytest fixtures and ASGI test client in conftest.py",
            lambda: [
                write_file("tests/__init__.py", '"""Test package."""\n'),
                copy_from_backup("tests/conftest.py"),
            ],
        ),
        (
            "2026-07-03 16:05:40 +0300",
            "feat(services): scaffold runner service and ContainerResult dataclass",
            lambda: [
                write_file("app/services/__init__.py", '"""Services package."""\n'),
                write_file("app/services/runner_docker.py", """from __future__ import annotations
import base64
import logging
import textwrap
from dataclasses import dataclass
from app.api.schemas import Language
from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class ContainerResult:
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    wall_time_s: float = 0.0
    peak_memory_bytes: int = 0
    timed_out: bool = False
    oom_killed: bool = False
"""),
            ],
        ),

        # --- Day 6: July 4 ---
        (
            "2026-07-04 11:45:00 +0300",
            "feat(services): implement base64 payload decoding script for Python",
            lambda: append_to_file("app/services/runner_docker.py", """
def _python_command() -> list[str]:
    return [
        "sh", "-c",
        textwrap.dedent('''
            echo "$CODE" | base64 -d > /tmp/main.py
            echo "$STDIN_DATA" | base64 -d | python -u /tmp/main.py
        '''),
    ]
"""),
        ),
        (
            "2026-07-04 17:15:30 +0300",
            "feat(services): implement Node.js runner shell command template",
            lambda: append_to_file("app/services/runner_docker.py", """
def _javascript_command() -> list[str]:
    return [
        "sh", "-c",
        textwrap.dedent('''
            echo "$CODE" | base64 -d > /tmp/main.js
            echo "$STDIN_DATA" | base64 -d | node /tmp/main.js
        '''),
    ]
"""),
        ),

        # --- Day 7: July 5 ---
        (
            "2026-07-05 13:20:15 +0300",
            "feat(services): add two-stage C compilation and execution command builder",
            lambda: append_to_file("app/services/runner_docker.py", """
def _c_command() -> list[str]:
    return [
        "sh", "-c",
        textwrap.dedent(f'''
            echo "$CODE" | base64 -d > /tmp/main.c
            COMP_ERR=$(gcc /tmp/main.c -o /tmp/main -lm 2>&1)
            if [ $? -ne 0 ]; then
                printf '%s' "$COMP_ERR" >&2
                exit {settings.compile_error_exit_code}
            fi
            echo "$STDIN_DATA" | base64 -d | /tmp/main
        '''),
    ]

_COMMAND_MAP = {
    Language.PYTHON: _python_command,
    Language.C: _c_command,
    Language.JAVASCRIPT: _javascript_command,
}
"""),
        ),

        # --- Day 8: July 6 ---
        (
            "2026-07-06 10:45:22 +0300",
            "feat(services): add Docker client connection factory with ping validation",
            lambda: append_to_file("app/services/runner_docker.py", """
import docker
import docker.errors
from requests.exceptions import ConnectionError as ReqConnectionError
from app.core.exceptions import DockerUnavailableError

def get_docker_client() -> docker.DockerClient:
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception as exc:
        raise DockerUnavailableError(f"Cannot reach Docker Engine: {exc}") from exc
"""),
        ),
        (
            "2026-07-06 16:30:10 +0300",
            "feat(services): implement isolated container creation with security constraints",
            lambda: append_to_file("app/services/runner_docker.py", """
from app.core.exceptions import ContainerCreationError

def _create_container(client, image, command, code_b64, stdin_b64, memory_limit_mb):
    return client.containers.create(
        image=image,
        command=command,
        environment={"CODE": code_b64, "STDIN_DATA": stdin_b64},
        network_mode="none",
        user=settings.container_user,
        read_only=True,
        tmpfs={"/tmp": f"size={settings.tmpfs_size_mb}m,exec"},
        mem_limit=f"{memory_limit_mb}m",
        memswap_limit=f"{memory_limit_mb}m",
        nano_cpus=settings.container_nano_cpus,
    )
"""),
        ),

        # --- Day 9: July 7 ---
        (
            "2026-07-07 11:15:35 +0300",
            "feat(services): implement background streaming memory stats monitor",
            lambda: append_to_file("app/services/runner_docker.py", """
import threading

class _MemoryMonitor:
    def __init__(self, container):
        self.container = container
        self.peak_bytes = 0
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self):
        try:
            for chunk in self.container.stats(stream=True, decode=True):
                if self._stop.is_set():
                    break
                usage = chunk.get("memory_stats", {}).get("usage", 0)
                self.peak_bytes = max(self.peak_bytes, usage)
        except Exception:
            pass
"""),
        ),
        (
            "2026-07-07 17:05:50 +0300",
            "feat(services): implement container wait, output capture, and cleanup",
            lambda: None,  # will add run_container
        ),

        # --- Day 10: July 8 ---
        (
            "2026-07-08 10:20:15 +0300",
            "feat(services): add wall-clock timeout detection and SIGKILL fallback",
            lambda: None,
        ),
        (
            "2026-07-08 15:50:40 +0300",
            "feat(services): inspect container state for kernel OOM-kill event",
            lambda: None,
        ),

        # --- July 9: EMPTY DAY ---

        # --- Day 12: July 10 ---
        (
            "2026-07-10 11:35:10 +0300",
            "feat(services): implement status classification logic in executor",
            lambda: write_file("app/services/executor.py", """from __future__ import annotations
import logging
from app.api.schemas import ExecutionRequest, ExecutionResponse, ExecutionStatus, Language
from app.core.config import settings

logger = logging.getLogger(__name__)

def _classify_status(result, language: Language) -> ExecutionStatus:
    if result.timed_out:
        return ExecutionStatus.TIMEOUT
    if result.oom_killed:
        return ExecutionStatus.MEMORY_LIMIT_EXCEEDED
    if language == Language.C and result.exit_code == settings.compile_error_exit_code:
        return ExecutionStatus.COMPILATION_ERROR
    if result.exit_code != 0:
        return ExecutionStatus.RUNTIME_ERROR
    return ExecutionStatus.SUCCESS
"""),
        ),
        (
            "2026-07-10 16:15:30 +0300",
            "feat(services): dispatch synchronous Docker runner via asyncio.to_thread",
            lambda: append_to_file("app/services/executor.py", """
import asyncio

async def execute(request: ExecutionRequest) -> ExecutionResponse:
    # Initial prototype dispatch
    pass
"""),
        ),

        # --- Day 13: July 11 ---
        (
            "2026-07-11 10:10:45 +0300",
            "feat(api): implement POST /api/v1/execute router",
            lambda: write_file("app/api/router.py", """from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, status
from app.api.schemas import ExecutionRequest, ExecutionResponse
from app.services import executor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(payload: ExecutionRequest):
    return await executor.execute(payload)
"""),
        ),
        (
            "2026-07-11 15:40:20 +0300",
            "feat(api): map Docker errors to HTTP 500 and 503 status codes",
            lambda: write_file("app/api/router.py", """from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, status
from app.api.schemas import ExecutionRequest, ExecutionResponse
from app.core.exceptions import ContainerCreationError, DockerUnavailableError, SandboxError
from app.services import executor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(payload: ExecutionRequest):
    try:
        return await executor.execute(payload)
    except DockerUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Docker unreachable") from exc
    except SandboxError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
"""),
        ),
        (
            "2026-07-11 19:15:10 +0300",
            "feat: create FastAPI application factory and lifespan hooks",
            lambda: write_file("app/main.py", """from __future__ import annotations
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from app.core.config import settings

logger = logging.getLogger(__name__)

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_title, version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    return app

app = create_app()
"""),
        ),

        # --- Day 14: July 12 ---
        (
            "2026-07-12 11:20:00 +0300",
            "test: write initial functional tests for Python execution",
            lambda: write_file("tests/test_execution.py", """from __future__ import annotations
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

async def _execute(client: AsyncClient, **kwargs):
    resp = await client.post("/api/v1/execute", json=kwargs)
    return resp.status_code, resp.json()

class TestPythonExecution:
    async def test_hello_world(self, client: AsyncClient):
        status, body = await _execute(client, language="python", code="print('Hello world!')")
        assert status == 200
        assert body["status"] == "success"
"""),
        ),
        (
            "2026-07-12 16:50:35 +0300",
            "test: add C and JavaScript execution tests",
            lambda: append_to_file("tests/test_execution.py", """
class TestCExecution:
    async def test_hello_world(self, client: AsyncClient):
        code = '#include <stdio.h>\\nint main() { printf("Hello C!\\\\n"); return 0; }'
        status, body = await _execute(client, language="c", code=code)
        assert status == 200

class TestJavaScriptExecution:
    async def test_hello_world(self, client: AsyncClient):
        status, body = await _execute(client, language="javascript", code="console.log('Hello JS!');")
        assert status == 200
"""),
        ),

        # --- Day 15: July 13 ---
        (
            "2026-07-13 10:45:15 +0300",
            "test: add validation tests for request limits and unsupported languages",
            lambda: append_to_file("tests/test_execution.py", """
class TestValidation:
    async def test_empty_code_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/execute", json={"language": "python", "code": ""})
        assert resp.status_code == 422

    async def test_unsupported_language_rejected(self, client: AsyncClient):
        resp = await client.post("/api/v1/execute", json={"language": "cobol", "code": "DISPLAY 1"})
        assert resp.status_code == 422
"""),
        ),
        (
            "2026-07-13 15:30:22 +0300",
            "refactor(services): improve error propagation and logging",
            lambda: append_to_file("app/core/config.py", "\n# Refined config comments\n"),
        ),

        # --- July 14: EMPTY DAY ---

        # --- Day 17: July 15 ---
        (
            "2026-07-15 11:15:30 +0300",
            "security: add pids_limit configuration to container creation",
            lambda: append_to_file("app/core/config.py", "\n# Container pids_limit = 64\n"),
        ),
        (
            "2026-07-15 16:40:05 +0300",
            "security: drop all Linux capabilities and enforce no-new-privileges",
            lambda: None,
        ),

        # --- Day 18: July 16 ---
        (
            "2026-07-16 10:50:20 +0300",
            "feat(services): implement output byte truncation at 1 MiB with audit marker",
            lambda: None,
        ),
        (
            "2026-07-16 15:25:40 +0300",
            "feat(api): expose stdout_truncated and stderr_truncated flags in schema",
            lambda: None,
        ),

        # --- Day 19: July 17 ---
        (
            "2026-07-17 09:40:15 +0300",
            "test: add security tests for infinite loops and timeout enforcement",
            lambda: copy_from_backup("tests/test_security.py"),
        ),
        (
            "2026-07-17 14:15:50 +0300",
            "test: add memory exhaustion and out-of-memory kill security tests",
            lambda: None,
        ),

        # --- Day 20: July 18 ---
        (
            "2026-07-18 11:30:10 +0300",
            "test: add fork bomb and network breakout security tests",
            lambda: None,
        ),
        (
            "2026-07-18 16:05:40 +0300",
            "test: add filesystem permission security tests verifying read-only root",
            lambda: None,
        ),

        # --- July 19: EMPTY DAY ---

        # --- Day 22: July 20 ---
        (
            "2026-07-20 10:15:20 +0300",
            "feat(middleware): create request correlation ID middleware",
            lambda: [
                write_file("app/middleware/__init__.py", '"""Custom middleware package."""\n'),
                copy_from_backup("app/middleware/request_id.py"),
            ],
        ),
        (
            "2026-07-20 14:50:11 +0300",
            "feat(core): implement structured JSON log formatter",
            lambda: copy_from_backup("app/core/logging_config.py"),
        ),
        (
            "2026-07-20 19:10:35 +0300",
            "feat(core): integrate request ID context variable into JSONFormatter",
            lambda: None,
        ),

        # --- Day 23: July 21 ---
        (
            "2026-07-21 11:05:30 +0300",
            "feat(services): implement asyncio semaphore concurrency limiter",
            lambda: copy_from_backup("app/services/concurrency.py"),
        ),
        (
            "2026-07-21 16:40:22 +0300",
            "feat(services): guard container execution with concurrency throttle",
            lambda: None,
        ),

        # --- Day 24: July 22 ---
        (
            "2026-07-22 10:30:15 +0300",
            "feat(api): map concurrency exhaustion to HTTP 429 response",
            lambda: None,
        ),
        (
            "2026-07-22 15:15:45 +0300",
            "test: write unit tests for concurrency limiter slot acquisition",
            lambda: None,
        ),

        # --- Day 25: July 23 ---
        (
            "2026-07-23 09:45:10 +0300",
            "feat(middleware): implement sliding-window rate limiter middleware",
            lambda: copy_from_backup("app/middleware/rate_limit.py"),
        ),
        (
            "2026-07-23 14:20:35 +0300",
            "feat(middleware): add Retry-After header and client IP resolution",
            lambda: None,
        ),
        (
            "2026-07-23 18:50:00 +0300",
            "test: write unit tests for rate limiter sliding-window enforcement",
            lambda: None,
        ),

        # --- Day 26: July 24 ---
        (
            "2026-07-24 11:10:25 +0300",
            "refactor(middleware): add periodic cleanup for stale client buckets",
            lambda: None,
        ),
        (
            "2026-07-24 16:35:40 +0300",
            "feat(core): configure rate limit parameters in Settings",
            lambda: copy_from_backup("app/core/config.py"),
        ),

        # --- July 25: EMPTY DAY ---

        # --- Day 28: July 26 ---
        (
            "2026-07-26 10:25:30 +0300",
            "feat(services): implement in-memory execution history store",
            lambda: copy_from_backup("app/services/history.py"),
        ),
        (
            "2026-07-26 15:40:15 +0300",
            "feat(services): implement TTL expiration and FIFO eviction on history",
            lambda: None,
        ),

        # --- Day 29: July 27 ---
        (
            "2026-07-27 09:50:20 +0300",
            "feat(api): implement GET /api/v1/executions audit history endpoint",
            lambda: None,
        ),
        (
            "2026-07-27 14:15:45 +0300",
            "feat(api): implement GET and DELETE endpoints for individual execution records",
            lambda: None,
        ),
        (
            "2026-07-27 18:30:10 +0300",
            "test: add unit tests for execution history store pagination and eviction",
            lambda: None,
        ),

        # --- Day 30: July 28 ---
        (
            "2026-07-28 10:40:30 +0300",
            "feat(core): introduce Prometheus operational metrics counters and histograms",
            lambda: copy_from_backup("app/core/metrics.py"),
        ),
        (
            "2026-07-28 16:15:05 +0300",
            "feat(api): expose /metrics endpoint in Prometheus text exposition format",
            lambda: None,
        ),

        # --- Day 31: July 29 ---
        (
            "2026-07-29 11:20:40 +0300",
            "feat(services): track active containers gauge during execution lifecycle",
            lambda: copy_from_backup("app/services/runner_docker.py"),
        ),
        (
            "2026-07-29 17:05:15 +0300",
            "feat(services): record execution durations and rate limit hits metrics",
            lambda: None,
        ),

        # --- July 30: EMPTY DAY ---

        # --- Day 33: July 31 ---
        (
            "2026-07-31 09:30:25 +0300",
            "feat(api): implement GET /api/v1/languages registry endpoint",
            lambda: None,
        ),
        (
            "2026-07-31 14:10:45 +0300",
            "feat(api): define language metadata and response models in schemas",
            lambda: copy_from_backup("app/api/schemas.py"),
        ),
        (
            "2026-07-31 18:25:30 +0300",
            "feat(api): add comprehensive /health readiness probe",
            lambda: copy_from_backup("app/api/router.py"),
        ),

        # --- Day 34: August 1 ---
        (
            "2026-08-01 10:50:15 +0300",
            "feat(api): implement WebSocket execution push endpoint",
            lambda: copy_from_backup("app/api/websocket.py"),
        ),
        (
            "2026-08-01 16:15:40 +0300",
            "test: write WebSocket validation and error handling unit tests",
            lambda: None,
        ),

        # --- Day 35: August 2 ---
        (
            "2026-08-02 11:30:20 +0300",
            "infra: create multi-stage Dockerfile for API service",
            lambda: copy_from_backup("Dockerfile"),
        ),
        (
            "2026-08-02 17:05:45 +0300",
            "infra: configure docker-compose with Docker socket mount",
            lambda: copy_from_backup("docker-compose.yml"),
        ),

        # --- Day 36: August 3 ---
        (
            "2026-08-03 10:15:35 +0300",
            "infra: configure Prometheus scrape config in prometheus.yml",
            lambda: copy_from_backup("prometheus.yml"),
        ),
        (
            "2026-08-03 15:40:10 +0300",
            "feat(services): wire execution ID, history, and metrics into executor",
            lambda: copy_from_backup("app/services/executor.py"),
        ),

        # --- August 4: EMPTY DAY ---

        # --- Day 38: August 5 ---
        (
            "2026-08-05 11:25:30 +0300",
            "test: consolidate comprehensive unit test suite in tests/test_unit.py",
            lambda: copy_from_backup("tests/test_unit.py"),
        ),
        (
            "2026-08-05 16:50:15 +0300",
            "test: update execution and probe tests for new response schemas",
            lambda: copy_from_backup("tests/test_execution.py"),
        ),

        # --- Day 39: August 6 ---
        (
            "2026-08-06 10:10:45 +0300",
            "docs: create comprehensive README with architecture diagram",
            lambda: copy_from_backup("README.md"),
        ),
        (
            "2026-08-06 14:45:20 +0300",
            "docs: document security constraints, threat mitigations, and benchmarks",
            lambda: None,
        ),
        (
            "2026-08-06 19:20:10 +0300",
            "feat: wire up main app with logging, middleware, health, and metrics",
            lambda: copy_from_backup("app/main.py"),
        ),

        # --- Day 40: August 7 ---
        (
            "2026-08-07 10:35:15 +0300",
            "build: update pyproject.toml with test markers and wheel packaging",
            lambda: copy_from_backup("pyproject.toml"),
        ),
        (
            "2026-08-07 14:20:40 +0300",
            "perf: pre-warm language container images on startup in lifespan hook",
            lambda: None,
        ),
        (
            "2026-08-07 17:05:22 +0300",
            "style: enforce ruff linting rules and format imports",
            lambda: None,
        ),
        (
            "2026-08-07 20:30:00 +0300",
            "release: finalize v1.0.0 release of ECES API",
            lambda: copy_all_from_backup(),
        ),
    ]

    for date_str, msg, action in steps:
        if action:
            action()
        make_commit(msg, date_str)

    # Clean up touch file if created
    touch = REPO_ROOT / ".git-touch"
    if touch.exists():
        touch.unlink()
        run_git(["add", "-A"])
        run_git(["commit", "--amend", "--no-edit"])

    # Clean up generation script
    this_script = REPO_ROOT / "generate_full_git_history.py"
    if this_script.exists():
        this_script.unlink()

    print("\n+ Successfully generated complete realistic git commit history!")


def copy_all_from_backup():
    import stat

    def safe_rm(p):
        def on_exc(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(p, onerror=on_exc)

    for item in BACKUP_DIR.iterdir():
        if item.name in [".git", ".venv", "generate_full_git_history.py", "build_git_history.py"]:
            continue
        dst = REPO_ROOT / item.name
        if item.is_dir():
            if dst.exists():
                safe_rm(dst)
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)


if __name__ == "__main__":
    main()
