"""Functional tests for API endpoints (/execute, /languages, /executions, /health, /metrics).

Tests with @pytest.mark.integration require a live Docker daemon.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _execute(client: AsyncClient, **kwargs) -> tuple[int, dict]:
    """POST to /api/v1/execute and return (status_code, json_body)."""
    resp = await client.post("/api/v1/execute", json=kwargs)
    return resp.status_code, resp.json()


# ---------------------------------------------------------------------------
# Metadata & Probe Endpoints (No Docker execution needed)
# ---------------------------------------------------------------------------

class TestProbesAndMetadata:
    async def test_health_endpoint(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "version" in data
        assert "docker_connected" in data
        assert "images_available" in data
        assert "active_executions" in data
        assert "max_concurrent" in data

    async def test_metrics_endpoint(self, client: AsyncClient):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]
        body = resp.text
        assert "eces_executions_total" in body
        assert "eces_active_containers" in body

    async def test_languages_endpoint(self, client: AsyncClient):
        resp = await client.get("/api/v1/languages")
        assert resp.status_code == 200
        data = resp.json()
        assert "languages" in data
        names = {item["name"] for item in data["languages"]}
        assert "python" in names
        assert "c" in names
        assert "javascript" in names

    async def test_request_id_header_injected(self, client: AsyncClient):
        resp = await client.get("/health")
        assert "x-request-id" in resp.headers
        assert len(resp.headers["x-request-id"]) > 0

    async def test_request_id_header_preserved(self, client: AsyncClient):
        custom_id = "test-custom-req-id-1234"
        resp = await client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp.headers.get("x-request-id") == custom_id


# ---------------------------------------------------------------------------
# Python execution
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPythonExecution:
    async def test_hello_world(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="python",
            code="print('Hello world!')",
        )
        assert status == 200
        assert body["status"] == "success"
        assert body["exit_code"] == 0
        assert "Hello world!" in body["stdout"]
        assert body["timed_out"] is False
        assert "execution_id" in body
        assert body["stdout_truncated"] is False
        assert body["stderr_truncated"] is False

    async def test_stdin_echo(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="python",
            code="import sys; print(sys.stdin.read().upper())",
            stdin="hello",
        )
        assert status == 200
        assert body["status"] == "success"
        assert "HELLO" in body["stdout"]

    async def test_stderr_capture(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="python",
            code="import sys; sys.stderr.write('oops\\n')",
        )
        assert status == 200
        assert "oops" in body["stderr"]

    async def test_nonzero_exit_code(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="python",
            code="import sys; sys.exit(42)",
        )
        assert status == 200
        assert body["status"] == "runtime_error"
        assert body["exit_code"] == 42

    async def test_syntax_error(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="python",
            code="def f(:\n  pass",
        )
        assert status == 200
        assert body["status"] == "runtime_error"
        assert body["exit_code"] != 0
        assert "SyntaxError" in body["stderr"]


# ---------------------------------------------------------------------------
# C execution
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCExecution:
    async def test_hello_world(self, client: AsyncClient):
        code = '#include <stdio.h>\nint main() { printf("Hello C!\\n"); return 0; }'
        status, body = await _execute(client, language="c", code=code)
        assert status == 200
        assert body["status"] == "success"
        assert "Hello C!" in body["stdout"]

    async def test_stdin(self, client: AsyncClient):
        code = (
            '#include <stdio.h>\n'
            'int main() { int x; scanf("%d", &x); printf("%d\\n", x * 2); return 0; }'
        )
        status, body = await _execute(client, language="c", code=code, stdin="21")
        assert status == 200
        assert "42" in body["stdout"]

    async def test_compilation_error(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="c",
            code="this is not valid C",
        )
        assert status == 200
        assert body["status"] == "compilation_error"


# ---------------------------------------------------------------------------
# JavaScript execution
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestJavaScriptExecution:
    async def test_hello_world(self, client: AsyncClient):
        status, body = await _execute(
            client,
            language="javascript",
            code="console.log('Hello JS!');",
        )
        assert status == 200
        assert body["status"] == "success"
        assert "Hello JS!" in body["stdout"]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    async def test_empty_code_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/execute",
            json={"language": "python", "code": ""},
        )
        assert resp.status_code == 422

    async def test_unsupported_language_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/execute",
            json={"language": "cobol", "code": "DISPLAY 'HI'."},
        )
        assert resp.status_code == 422

    async def test_timeout_too_large_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/execute",
            json={"language": "python", "code": "pass", "timeout_seconds": 999},
        )
        assert resp.status_code == 422

    async def test_memory_too_large_rejected(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/execute",
            json={"language": "python", "code": "pass", "memory_limit_mb": 9999},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# History and Audit Trail
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestHistoryEndpoints:
    async def test_execution_recorded_in_history(self, client: AsyncClient):
        # Run code
        status, body = await _execute(
            client,
            language="python",
            code="print('history check')",
        )
        assert status == 200
        exec_id = body["execution_id"]

        # Fetch history list
        list_resp = await client.get("/api/v1/executions")
        assert list_resp.status_code == 200
        hist_data = list_resp.json()
        assert hist_data["total"] >= 1
        ids = [e["id"] for e in hist_data["executions"]]
        assert exec_id in ids

        # Fetch single execution detail
        detail_resp = await client.get(f"/api/v1/executions/{exec_id}")
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert detail_data["id"] == exec_id
        assert detail_data["language"] == "python"
        assert detail_data["request"]["code"] == "print('history check')"
        assert detail_data["response"]["status"] == "success"

        # Delete execution record
        del_resp = await client.delete(f"/api/v1/executions/{exec_id}")
        assert del_resp.status_code == 204

        # Confirm deleted
        del_check = await client.get(f"/api/v1/executions/{exec_id}")
        assert del_check.status_code == 404
