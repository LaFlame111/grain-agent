from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from .domain import Reading, GrainTempData, GasConcentrationData, WarehouseInfo

# --- 基础响应模型 ---
class BaseResponse(BaseModel):
    trace_id: str = Field(..., description="追踪ID")

# --- 业务数据响应 (对应 T2) ---
class GrainTempResponse(BaseResponse):
    data: List[GrainTempData]

class GasConcentrationResponse(BaseResponse):
    data: List[GasConcentrationData]

class WarehouseInfoResponse(BaseResponse):
    data: WarehouseInfo

# --- 巡检 (T1) ---
class InspectionProfile(BaseModel):
    temp_max: float = 30.0
    co2_max: float = 5000.0

class InspectionRequest(BaseModel):
    warehouse_ids: Optional[List[str]] = None
    inspection_profile: InspectionProfile = InspectionProfile()
    timestamp: Optional[datetime] = None

class InspectionPointResult(BaseModel):
    warehouse_id: str
    silo_id: str
    point_id: str
    status: str # normal, abnormal
    type: Optional[str] = None
    advice: Optional[str] = None

class InspectionSummary(BaseModel):
    abnormal_points: int
    total_points: int

class InspectionResponse(BaseResponse):
    results: List[InspectionPointResult]
    summary: InspectionSummary

# --- 分析 (T3/T4/T5) ---
class AnalysisRequest(BaseModel):
    silo_id: str
    start_time: datetime
    end_time: datetime
    analysis_type: str = "basic" # basic, trend, hotspot

class AnalysisResult(BaseModel):
    silo_id: str
    analysis_type: str
    findings: List[str]
    risk_level: str # low, medium, high
    score: float
    hotspots: List[Dict[str, Any]] = []
    trends: List[Dict[str, Any]] = []
    recommendations: List[str] = []

class AnalysisResponse(BaseResponse):
    data: AnalysisResult

# --- LLM 推理 (T6) ---
class LLMReasoningRequest(BaseModel):
    context: Dict[str, Any] # 包含 T1-T5 的结果
    prompt_template: Optional[str] = None

class LLMReasoningResponse(BaseResponse):
    conclusion: str
    risk_level: str
    recommendations: List[str]
    evidence: List[str] = []

# --- Agent 对话 (Chat) ---
class AgentChatRequest(BaseModel):
    """Agent 对话请求"""
    query: str  # 用户的自然语言查询
    session_id: Optional[str] = None  # 会话ID（可选）
    history: List[Dict[str, str]] = [] # 历史对话

class AgentChatResponse(BaseResponse):
    """Agent 对话响应"""
    query: str  # 用户查询
    intent: str  # 识别的意图
    answer: str  # Agent 的回答
    reasoning: str  # 推理过程
    tool_calls: List[Dict[str, Any]]  # 调用的工具列表
    raw_results: Dict[str, Any]  # 原始结果
    timestamp: datetime

class LLMStructuredResponse(BaseModel):
    """LLM 结构化输出 Schema"""
    answer: str
    reasoning: str


