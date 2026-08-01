"""WebSocket endpoint for real-time, push-based code execution."""

from __future__ import annotations

import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.api.schemas import ExecutionRequest
from app.core.exceptions import SandboxError
from app.services import executor
from app.services.concurrency import ConcurrencyExhaustedError

logger = logging.getLogger(__name__)

ws_router = APIRouter()


@ws_router.websocket("/api/v1/execute/ws")
async def websocket_execute(websocket: WebSocket) -> None:
    """Accept and process code execution requests over a persistent WebSocket.

    Handles the full lifecycle of a single WebSocket execution session:
    accepts the connection, receives the JSON payload, validates and executes
    the code inside the sandbox, streams the result back, and closes the connection.

    Args:
        websocket: The active WebSocket connection from the client.
    """
    await websocket.accept()
    logger.info("Accepted WebSocket execution connection from %s", websocket.client)
    try:
        # Receive JSON matching ExecutionRequest schema
        data = await websocket.receive_json()
        request = ExecutionRequest(**data)

        # Execute
        response = await executor.execute(request)

        # Send result
        await websocket.send_json({"type": "result", "data": response.model_dump()})
    except ValidationError as exc:
        logger.warning("WebSocket payload validation failed: %s", exc)
        await websocket.send_json({"type": "error", "data": {"detail": str(exc)}})
    except ConcurrencyExhaustedError:
        logger.warning("WebSocket execution rejected: concurrency limit reached")
        await websocket.send_json(
            {"type": "error", "data": {"detail": "Server is at capacity. Try again later."}}
        )
    except SandboxError as exc:
        logger.error("WebSocket sandbox execution error: %s", exc)
        await websocket.send_json({"type": "error", "data": {"detail": str(exc)}})
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected prematurely")
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
