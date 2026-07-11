from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, status
from app.api.schemas import ExecutionRequest, ExecutionResponse
from app.services import executor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

@router.post("/execute", response_model=ExecutionResponse)
async def execute_code(payload: ExecutionRequest):
    return await executor.execute(payload)
