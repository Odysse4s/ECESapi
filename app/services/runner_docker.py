from __future__ import annotations
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
