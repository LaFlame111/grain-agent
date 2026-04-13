import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（使用绝对路径，确保从任意目录启动都能找到）
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # V008/
env_file = BASE_DIR / ".env"
load_dotenv(env_file, override=True)

logger = logging.getLogger(__name__)


class Settings:
    PROJECT_NAME: str = "Grain Agent V008 - Evolutionary Version"
    API_V1_STR: str = "/api/v1"

    # LLM 配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-max")
    LLM_BASE_URL: str = os.getenv(
        "LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    # 单次 LLM 调用超时（秒）。本地模型推理慢，建议设 120~300；云端模型可保持 30~60
    LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "120"))

    # Embedding 配置（RAG 知识检索）
    # 兼容“语言大模型”和“embedding 大模型”使用不同服务的情况
    EMBEDDING_API_KEY: str = os.getenv(
        "EMBEDDING_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")
    )
    EMBEDDING_BASE_URL: str = os.getenv(
        "EMBEDDING_BASE_URL", os.getenv("LLM_BASE_URL", "")
    )
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")
    EMBEDDING_DIMENSIONS: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))

    # 调试模式
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # A: 对外严格只暴露 /api/v1/agent/chat
    # - 当 DEBUG=false 时：关闭 docs/openapi/root，并且禁用 chat 之外的辅助端点
    EXPOSE_DOCS: bool = os.getenv("EXPOSE_DOCS", "false").lower() == "true"
    EXPOSE_DEBUG_ENDPOINTS: bool = (
        os.getenv("EXPOSE_DEBUG_ENDPOINTS", "false").lower() == "true"
    )

    # WMS API 配置
    WMS_BASE_URL: str = os.getenv("WMS_BASE_URL", "http://121.40.162.1:8017")

    # RAGFlow 配置
    RAGFLOW_API_KEY: str = os.getenv("RAGFLOW_API_KEY", "")
    RAGFLOW_BASE_URL: str = os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380")
    RAGFLOW_DATASET_IDS: str = os.getenv(
        "RAGFLOW_DATASET_IDS", ""
    )  # 逗号分隔多个 dataset id

    # RAG 增强层配置（rerank_clean 最优参数，经消融实验验证）
    RAG_SIMILARITY_THRESHOLD: float = float(
        os.getenv("RAG_SIMILARITY_THRESHOLD", "0.1")
    )
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RAG_PAGE_SIZE: int = int(os.getenv("RAG_PAGE_SIZE", "15"))
    RAG_RERANK_ID: str = os.getenv("RAG_RERANK_ID", "gte-rerank")
    RAG_ENABLE_QUERY_REWRITE: bool = (
        os.getenv("RAG_ENABLE_QUERY_REWRITE", "false").lower() == "true"
    )
    RAG_QUERY_REWRITE_MODEL: str = os.getenv(
        "RAG_QUERY_REWRITE_MODEL", ""
    )  # 空则复用 LLM_MODEL

    def __init__(self):
        # 验证 API Key 是否加载成功
        if not self.DASHSCOPE_API_KEY and not self.EMBEDDING_API_KEY:
            print(
                f"[WARN] DASHSCOPE_API_KEY / EMBEDDING_API_KEY 均未设置! (检查文件: {env_file})"
            )
        else:
            # 避免在日志里泄露完整密钥，只输出开头/结尾长度
            if self.DASHSCOPE_API_KEY:
                print(
                    f"[OK] 已加载 DASHSCOPE_API_KEY: {self.DASHSCOPE_API_KEY[:6]}...{self.DASHSCOPE_API_KEY[-4:]}"
                )
            if self.EMBEDDING_API_KEY:
                print(
                    f"[OK] 已加载 EMBEDDING_API_KEY: {self.EMBEDDING_API_KEY[:6]}...{self.EMBEDDING_API_KEY[-4:]}"
                )


settings = Settings()
