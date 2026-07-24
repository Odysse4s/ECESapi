"""Application configuration loaded from environment variables with sensible defaults."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration — every field can be overridden via an env var of the same name."""

    # ── API ──────────────────────────────────────────────────────────────
    app_title: str = "ECES API"
    app_description: str = (
        "Ephemeral Code Execution Sandbox — execute untrusted code "
        "in isolated Docker containers with strict resource constraints."
    )
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Execution defaults ───────────────────────────────────────────────
    default_timeout_seconds: float = 5.0
    max_timeout_seconds: float = 30.0
    default_memory_limit_mb: int = 64
    max_memory_limit_mb: int = 128
    max_code_size_bytes: int = 65_536  # 64 KiB
    max_output_bytes: int = 1_048_576  # 1 MiB per stream

    # ── Docker images per language ───────────────────────────────────────
    image_python: str = "python:3.12-alpine"
    image_c: str = "gcc:14-bookworm"
    image_javascript: str = "node:22-alpine"

    # ── Container security constraints ───────────────────────────────────
    container_user: str = "1000:1000"
    container_nano_cpus: int = 1_000_000_000  # 1 vCPU
    container_pids_limit: int = 64
    tmpfs_size_mb: int = 64

    # ── Sentinel exit code emitted by the compile wrapper on failure ─────
    compile_error_exit_code: int = 252

    # ── Rate limiting ────────────────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60

    # ── Concurrency ──────────────────────────────────────────────────────
    max_concurrent_executions: int = 10

    # ── Execution history ────────────────────────────────────────────────
    history_enabled: bool = True
    history_ttl_seconds: int = 3600  # 1 hour
    history_max_entries: int = 1000

    model_config = {"env_prefix": "ECES_"}


settings = Settings()
