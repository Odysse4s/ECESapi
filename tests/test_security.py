"""Security-focused tests that verify sandbox isolation constraints.

Each test deliberately tries to break out of the sandbox and asserts that the
attempt is contained (timeout, OOM, permission denied, etc.).

These require a live Docker daemon.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def _execute(client: AsyncClient, **kwargs) -> dict:
    resp = await client.post("/api/v1/execute", json=kwargs)
    return resp.json()


# ---------------------------------------------------------------------------
# Timeout enforcement
# ---------------------------------------------------------------------------

class TestTimeout:
    async def test_infinite_loop_python(self, client: AsyncClient):
        body = await _execute(
            client,
            language="python",
            code="while True: pass",
            timeout_seconds=2,
        )
        assert body["status"] == "timeout"
        assert body["timed_out"] is True

    async def test_sleep_exceeding_timeout(self, client: AsyncClient):
        body = await _execute(
            client,
            language="python",
            code="import time; time.sleep(60)",
            timeout_seconds=2,
        )
        assert body["status"] == "timeout"
        assert body["timed_out"] is True

    async def test_infinite_loop_c(self, client: AsyncClient):
        code = "int main() { while(1); return 0; }"
        body = await _execute(
            client,
            language="c",
            code=code,
            timeout_seconds=2,
        )
        assert body["status"] == "timeout"

    async def test_infinite_loop_js(self, client: AsyncClient):
        body = await _execute(
            client,
            language="javascript",
            code="while(true) {}",
            timeout_seconds=2,
        )
        assert body["status"] == "timeout"


# ---------------------------------------------------------------------------
# Memory-limit enforcement
# ---------------------------------------------------------------------------

class TestMemoryLimit:
    async def test_oom_python(self, client: AsyncClient):
        """Attempt to allocate far more than the memory ceiling."""
        body = await _execute(
            client,
            language="python",
            code="x = [bytearray(10**7) for _ in range(100)]",
            memory_limit_mb=16,
            timeout_seconds=10,
        )
        assert body["status"] in ("memory_limit_exceeded", "runtime_error")

    async def test_oom_c(self, client: AsyncClient):
        code = (
            '#include <stdlib.h>\n'
            'int main() {\n'
            '    for (int i = 0; i < 1000; i++) {\n'
            '        char *p = malloc(10 * 1024 * 1024);\n'
            '        if (!p) return 1;\n'
            '        for (int j = 0; j < 10*1024*1024; j++) p[j] = 1;\n'
            '    }\n'
            '    return 0;\n'
            '}'
        )
        body = await _execute(
            client,
            language="c",
            code=code,
            memory_limit_mb=16,
            timeout_seconds=10,
        )
        assert body["status"] in ("memory_limit_exceeded", "runtime_error")


# ---------------------------------------------------------------------------
# Fork bomb mitigation (pids_limit = 64)
# ---------------------------------------------------------------------------

class TestForkBomb:
    async def test_fork_bomb_python(self, client: AsyncClient):
        body = await _execute(
            client,
            language="python",
            code="import os\nwhile True:\n    os.fork()",
            timeout_seconds=5,
        )
        # Should either error out or timeout — never succeed silently.
        assert body["status"] in ("runtime_error", "timeout", "memory_limit_exceeded")

    async def test_fork_bomb_c(self, client: AsyncClient):
        code = (
            '#include <unistd.h>\n'
            'int main() { while(1) fork(); return 0; }'
        )
        body = await _execute(
            client,
            language="c",
            code=code,
            timeout_seconds=5,
        )
        assert body["status"] in ("runtime_error", "timeout", "memory_limit_exceeded")


# ---------------------------------------------------------------------------
# Network isolation
# ---------------------------------------------------------------------------

class TestNetworkIsolation:
    async def test_network_disabled_python(self, client: AsyncClient):
        body = await _execute(
            client,
            language="python",
            code=(
                "import socket\n"
                "s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
                "s.settimeout(2)\n"
                "s.connect(('8.8.8.8', 53))\n"
            ),
            timeout_seconds=5,
        )
        assert body["status"] == "runtime_error"
        assert body["exit_code"] != 0

    async def test_network_disabled_js(self, client: AsyncClient):
        body = await _execute(
            client,
            language="javascript",
            code=(
                "const http = require('http');\n"
                "http.get('http://example.com', (r) => console.log(r.statusCode));\n"
            ),
            timeout_seconds=5,
        )
        # Should fail — network unreachable.
        assert body["status"] in ("runtime_error", "timeout")


# ---------------------------------------------------------------------------
# Filesystem isolation
# ---------------------------------------------------------------------------

class TestFilesystemIsolation:
    async def test_write_outside_tmp_denied(self, client: AsyncClient):
        """Root FS is read-only; writes outside /tmp must fail."""
        body = await _execute(
            client,
            language="python",
            code="open('/etc/pwned', 'w').write('nope')",
            timeout_seconds=5,
        )
        assert body["status"] == "runtime_error"
        assert body["exit_code"] != 0

    async def test_write_to_tmp_allowed(self, client: AsyncClient):
        """Writes to /tmp (tmpfs) should succeed."""
        body = await _execute(
            client,
            language="python",
            code=(
                "with open('/tmp/test.txt', 'w') as f:\n"
                "    f.write('ok')\n"
                "with open('/tmp/test.txt') as f:\n"
                "    print(f.read())\n"
            ),
            timeout_seconds=5,
        )
        assert body["status"] == "success"
        assert "ok" in body["stdout"]

    async def test_read_sensitive_files(self, client: AsyncClient):
        """Container user (1000:1000) should not read host-only paths."""
        body = await _execute(
            client,
            language="python",
            code="print(open('/etc/shadow').read())",
            timeout_seconds=5,
        )
        # Either permission denied (runtime_error) or file doesn't exist
        # in the alpine image.
        assert body["status"] == "runtime_error"
