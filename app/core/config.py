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
    model_config = {"env_prefix": "ECES_"}

settings = Settings()
