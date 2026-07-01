from __future__ import annotations
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
