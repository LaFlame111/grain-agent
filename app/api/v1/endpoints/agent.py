"""
Agent 端点 - 基于意图识别的智能对话

用户通过自然语言提问，Agent 自动选择和调用合适的工具
"""

from fastapi import APIRouter
from typing import Dict, Any, List
from datetime import datetime
import uuid
import logging
import time

from app.models.schemas import AgentChatRequest, AgentChatResponse
from app.services.agent_service import AgentService

router = APIRouter()
logger = logging.getLogger(__name__)

# 全局 Agent 实例（保持对话历史）
try:
    logger.info("Initializing AgentService...")
    agent = AgentService()
    logger.info("AgentService initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize AgentService: {e}", exc_info=True)
    raise


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest):
    """
    Agent 智能对话接口
    
    用户可以用自然语言提问，Agent 会：
    1. 识别用户意图
    2. 自动选择合适的工具（T1-T8）
    3. 执行工具链
    4. 生成回答
    
    支持的查询类型：
    - 单仓查询: "1号仓的粮温情况如何？"
    - 仓间对比: "1号仓和2号仓哪个温度更高？"
    - 时间对比: "1号仓这周温度比上周高吗？"
    - 全库巡检: "巡检一下所有粮仓"
    
    示例请求:
    {
        "query": "1号仓的粮温情况如何？请给出储藏建议。"
    }
    """
    
    try:
        # 调用 Agent 处理查询
        logger.info(f"Processing query: {request.query[:50]}...")
        start_time = time.time()
        response = agent.chat(request.query)
        elapsed = time.time() - start_time
        logger.info(f"Query processed in {elapsed:.2f}s")
        
        # 添加时间戳和 trace_id
        response["timestamp"] = datetime.now()
        response["trace_id"] = str(uuid.uuid4())
        
        return AgentChatResponse(**response)
    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise
