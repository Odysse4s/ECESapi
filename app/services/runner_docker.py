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

def _python_command() -> list[str]:
    return [
        "sh", "-c",
        textwrap.dedent('''
            echo "$CODE" | base64 -d > /tmp/main.py
            echo "$STDIN_DATA" | base64 -d | python -u /tmp/main.py
        '''),
    ]

def _javascript_command() -> list[str]:
    return [
        "sh", "-c",
        textwrap.dedent('''
            echo "$CODE" | base64 -d > /tmp/main.js
            echo "$STDIN_DATA" | base64 -d | node /tmp/main.js
        '''),
    ]

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
