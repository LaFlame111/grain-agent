from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.v1.api import api_router
import time
import uuid
import logging
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

_docs_enabled = settings.DEBUG or settings.EXPOSE_DOCS
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="粮情分析智能体 - 纯 Agent 模式：仅提供自然语言对话接口，后台自动调用工具。",
    version="0.0.8",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# 配置 CORS - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境）
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    logger.info(f"Request started: {request.method} {request.url} [ID: {request_id}]")
    
    try:
        response = await call_next(request)
        
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id
        
        logger.info(f"Request completed: {request.method} {request.url} [ID: {request_id}] - Took {process_time:.4f}s")
        
        return response
    except Exception as e:
        logger.error(f"Request failed: {e}", exc_info=True)
        raise

@app.get("/")
def read_root():
    """根路径 - 始终可用，用于健康检查"""
    return {
        "message": "Grain Agent V008 is running",
        "mode": "Agent-Only (Natural Language Interface)",
        "description": "V008：进化版本，在 V007 基础上进行能力增强和架构优化。",
        "docs_enabled": settings.DEBUG or settings.EXPOSE_DOCS,
        "docs_url": "/docs" if (settings.DEBUG or settings.EXPOSE_DOCS) else None,
        "llm_status": "configured" if settings.DASHSCOPE_API_KEY else "missing_key",
        "key_len": len(settings.DASHSCOPE_API_KEY) if settings.DASHSCOPE_API_KEY else 0
    }

app.include_router(api_router, prefix=settings.API_V1_STR)

# 挂载静态文件目录，用于访问生成的图表和报告
artifacts_path = os.path.join(os.path.dirname(__file__), "..", "artifacts")
if not os.path.exists(artifacts_path):
    os.makedirs(artifacts_path, exist_ok=True)
app.mount("/artifacts", StaticFiles(directory=artifacts_path), name="artifacts")

# 启动时日志
logger.info(f"FastAPI app initialized. DEBUG={settings.DEBUG}, EXPOSE_DOCS={settings.EXPOSE_DOCS}")

