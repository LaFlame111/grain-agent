from fastapi import APIRouter
from app.api.v1.endpoints import agent

api_router = APIRouter()

# Agent 智能对话接口（核心功能）
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])


