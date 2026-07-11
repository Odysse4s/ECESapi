from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, status
from app.api.schemas import ExecutionRequest, ExecutionResponse
from app.core.exceptions import ContainerCreationError, DockerUnavailableError, SandboxError
from app.services import executor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(payload: ExecutionRequest):
    try:
        return await executor.execute(payload)
    except DockerUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Docker unreachable") from exc
    except SandboxError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
