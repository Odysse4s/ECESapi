from __future__ import annotations
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
