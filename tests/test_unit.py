"""Unit tests for middleware, services, and core utilities.

These tests do NOT require a live Docker daemon and run purely in-memory.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.core.exceptions import ConcurrencyExhaustedError
from app.core.logging_config import JSONFormatter
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import REQUEST_ID_CTX_VAR, RequestIDMiddleware
from app.services.concurrency import ConcurrencyLimiter
from app.services.history import ExecutionHistory

# ---------------------------------------------------------------------------
# Concurrency Limiter Tests
# ---------------------------------------------------------------------------

class TestConcurrencyLimiter:
    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        limiter = ConcurrencyLimiter(max_concurrent=2)
        assert limiter.active_count == 0
        assert limiter.max_concurrent == 2

        async with limiter.throttle():
            assert limiter.active_count == 1

        assert limiter.active_count == 0

    @pytest.mark.asyncio
    async def test_exhaustion_raises_error(self):
        limiter = ConcurrencyLimiter(max_concurrent=1)

        async def slow_task():
            async with limiter.throttle():
                await asyncio.sleep(0.8)

        task = asyncio.create_task(slow_task())
        await asyncio.sleep(0.05)  # Let slow_task acquire slot

        # Second acquisition should fail with ConcurrencyExhaustedError after 0.5s timeout
        with pytest.raises(ConcurrencyExhaustedError):
            async with limiter.throttle():
                pass

        await task


# ---------------------------------------------------------------------------
# Execution History Store Tests
# ---------------------------------------------------------------------------

class TestExecutionHistory:
    def test_create_and_get(self):
        store = ExecutionHistory(max_entries=10, ttl_seconds=3600)
        rec = store.create(
            execution_id="test-1",
            request_dict={"language": "python", "code": "print(1)"},
            language="python",
            code="print(1)",
        )
        assert rec.id == "test-1"
        assert rec.language == "python"
        assert rec.status is None
        assert rec.response is None

        fetched = store.get("test-1")
        assert fetched is not None
        assert fetched.id == "test-1"

    def test_complete_record(self):
        store = ExecutionHistory(max_entries=10, ttl_seconds=3600)
        store.create("test-2", {"code": "x=1"}, "python", "x=1")
        store.complete("test-2", {"status": "success", "exit_code": 0})

        rec = store.get("test-2")
        assert rec is not None
        assert rec.status == "success"
        assert rec.response["exit_code"] == 0
        assert rec.completed_at is not None

    def test_delete_record(self):
        store = ExecutionHistory(max_entries=10, ttl_seconds=3600)
        store.create("test-del", {}, "python", "pass")
        assert store.delete("test-del") is True
        assert store.get("test-del") is None
        assert store.delete("non-existent") is False

    def test_pagination_and_ordering(self):
        store = ExecutionHistory(max_entries=10, ttl_seconds=3600)
        for i in range(5):
            store.create(f"id-{i}", {}, "python", f"code-{i}")

        items, total = store.list_recent(limit=2, offset=0)
        assert total == 5
        assert len(items) == 2
        # Most recent first
        assert items[0].id == "id-4"
        assert items[1].id == "id-3"

        items_offset, _ = store.list_recent(limit=2, offset=2)
        assert len(items_offset) == 2
        assert items_offset[0].id == "id-2"
        assert items_offset[1].id == "id-1"

    def test_max_capacity_eviction(self):
        store = ExecutionHistory(max_entries=3, ttl_seconds=3600)
        store.create("e-1", {}, "python", "1")
        store.create("e-2", {}, "python", "2")
        store.create("e-3", {}, "python", "3")
        store.create("e-4", {}, "python", "4")  # Should evict e-1

        assert store.get("e-1") is None
        assert store.get("e-4") is not None
        _, total = store.list_recent()
        assert total == 3


# ---------------------------------------------------------------------------
# Rate Limit Middleware Tests
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        async def dummy_endpoint(request):
            return JSONResponse({"status": "ok"})

        test_app = Starlette(
            routes=[Route("/api/test", dummy_endpoint)],
        )
        test_app.add_middleware(
            RateLimitMiddleware,
            enabled=True,
            max_requests=3,
            window_seconds=10,
        )

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 3 requests within limit
            for _ in range(3):
                resp = await client.get("/api/test")
                assert resp.status_code == 200

            # 4th request must be rejected with 429
            resp = await client.get("/api/test")
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
            assert "Too many requests" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_non_api_paths_bypass_rate_limit(self):
        async def health_endpoint(request):
            return JSONResponse({"health": "ok"})

        test_app = Starlette(
            routes=[Route("/health", health_endpoint)],
        )
        test_app.add_middleware(
            RateLimitMiddleware,
            enabled=True,
            max_requests=1,
            window_seconds=10,
        )

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.get("/health")
            resp2 = await client.get("/health")
            assert resp1.status_code == 200
            assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Request ID Middleware Tests
# ---------------------------------------------------------------------------

class TestRequestIDMiddleware:
    @pytest.mark.asyncio
    async def test_request_id_generated(self):
        async def test_endpoint(request):
            return JSONResponse({"status": "ok"})

        test_app = Starlette(
            routes=[Route("/test", test_endpoint)],
        )
        test_app.add_middleware(RequestIDMiddleware)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/test")
            assert "x-request-id" in resp.headers
            req_id = resp.headers["x-request-id"]
            assert len(req_id) == 36  # UUID4 length

    @pytest.mark.asyncio
    async def test_request_id_preserved(self):
        async def test_endpoint(request):
            return JSONResponse({"status": "ok"})

        test_app = Starlette(
            routes=[Route("/test", test_endpoint)],
        )
        test_app.add_middleware(RequestIDMiddleware)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/test", headers={"X-Request-ID": "custom-uuid-999"})
            assert resp.headers["x-request-id"] == "custom-uuid-999"


# ---------------------------------------------------------------------------
# Structured Logging Tests
# ---------------------------------------------------------------------------

class TestJSONFormatter:
    def test_json_formatter_fields(self):
        formatter = JSONFormatter()
        REQUEST_ID_CTX_VAR.set("req-test-456")

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="User %s did %s",
            args=("alice", "login"),
            exc_info=None,
        )

        formatted_str = formatter.format(record)
        data = json.loads(formatted_str)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "User alice did login"
        assert data["request_id"] == "req-test-456"
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# WebSocket Endpoint Tests
# ---------------------------------------------------------------------------

class TestWebSocket:
    def test_websocket_invalid_payload_returns_error(self):
        from starlette.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        with client.websocket_connect("/api/v1/execute/ws") as ws:
            ws.send_json({"language": "python", "code": ""})  # invalid: empty code
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "detail" in response["data"]

