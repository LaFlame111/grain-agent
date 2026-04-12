"""
RAGFlow 知识库初始化脚本

功能:
  1. 在 RAGFlow 中创建数据集 (grain_knowledge)
  2. 上传 data/knowledge/ 目录下的所有知识文档
  3. 触发异步文档解析
  4. 输出 dataset_id 供 .env 配置使用

用法:
    cd V008
    python -m scripts.init_ragflow_knowledge

前置条件:
    - RAGFlow 已通过 Docker 部署并运行
    - 已在 .env 中配置 RAGFLOW_API_KEY 和 RAGFLOW_BASE_URL
"""

import os
import sys
import time
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中
BASE_DIR = Path(__file__).resolve().parent.parent  # V008/
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env", override=True)

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# --------------- 配置 ---------------
KNOWLEDGE_DIR = BASE_DIR / "data" / "knowledge"
DATASET_NAME = "grain_knowledge"
SUPPORTED_EXTS = {".md", ".txt", ".docx", ".pdf", ".xlsx", ".pptx"}

# 分块策略: naive(通用), laws(法规), book(书籍), paper(论文), qa(问答对)
CHUNK_METHOD = "naive"


def get_config():
    """获取 RAGFlow 配置"""
    api_key = os.getenv("RAGFLOW_API_KEY", "")
    base_url = os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:9380")

    if not api_key:
        logger.error("RAGFLOW_API_KEY 未配置！请在 .env 中设置。")
        logger.info("提示: 在 RAGFlow Web UI (http://localhost:80) 的用户设置中获取 API Key")
        sys.exit(1)

    return api_key, base_url


def create_client(api_key: str, base_url: str) -> httpx.Client:
    """创建 HTTP 客户端"""
    return httpx.Client(
        base_url=base_url,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout=60.0,
    )


def find_or_create_dataset(client: httpx.Client) -> str:
    """查找或创建数据集，返回 dataset_id"""
    # 先查找是否已存在
    resp = client.get("/api/v1/datasets", params={"page": 1, "page_size": 100})
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            for ds in data.get("data", []):
                if ds.get("name") == DATASET_NAME:
                    dataset_id = ds.get("id")
                    logger.info(f"数据集已存在: {DATASET_NAME} (ID: {dataset_id})")
                    return dataset_id

    # 不存在则创建
    logger.info(f"创建数据集: {DATASET_NAME} (分块策略: {CHUNK_METHOD})")
    payload = {
        "name": DATASET_NAME,
        "chunk_method": CHUNK_METHOD,
        "description": "粮情分析智能体知识库 - 包含国标/SOP/安全阈值等专业知识",
    }
    resp = client.post("/api/v1/datasets", json=payload)

    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            dataset_id = data.get("data", {}).get("id", "")
            logger.info(f"数据集创建成功: {DATASET_NAME} (ID: {dataset_id})")
            return dataset_id

    logger.error(f"数据集创建失败: {resp.status_code} - {resp.text}")
    sys.exit(1)


def get_existing_documents(client: httpx.Client, dataset_id: str) -> set:
    """获取数据集中已有文档的名称列表"""
    existing = set()
    resp = client.get(
        f"/api/v1/datasets/{dataset_id}/documents",
        params={"page": 1, "page_size": 100},
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            for doc in data.get("data", {}).get("docs", []):
                existing.add(doc.get("name", ""))
    return existing


def upload_documents(client: httpx.Client, dataset_id: str) -> list:
    """上传知识文档到数据集，返回新上传的文档 ID 列表"""
    if not KNOWLEDGE_DIR.exists():
        logger.error(f"知识目录不存在: {KNOWLEDGE_DIR}")
        logger.info("请创建 data/knowledge/ 目录并放入知识文档")
        return []

    # 收集待上传文件
    files = []
    for ext in SUPPORTED_EXTS:
        files.extend(KNOWLEDGE_DIR.glob(f"*{ext}"))

    if not files:
        logger.warning(f"知识目录中未找到支持的文件: {KNOWLEDGE_DIR}")
        return []

    # 获取已有文档，避免重复上传
    existing = get_existing_documents(client, dataset_id)
    logger.info(f"数据集中已有 {len(existing)} 个文档")

    uploaded_ids = []
    for fpath in sorted(files):
        if fpath.name in existing:
            logger.info(f"  跳过（已存在）: {fpath.name}")
            continue

        logger.info(f"  上传: {fpath.name} ({fpath.stat().st_size / 1024:.1f} KB)")

        # 上传文件使用 multipart/form-data（需要独立请求，不能带 JSON Content-Type）
        api_key = client.headers["Authorization"].split(" ")[1]
        with open(fpath, "rb") as f:
            resp = httpx.post(
                f"{client.base_url}/api/v1/datasets/{dataset_id}/documents",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (fpath.name, f)},
                timeout=60.0,
            )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                docs = data.get("data", [])
                for doc in docs:
                    uploaded_ids.append(doc.get("id", ""))
                logger.info(f"  上传成功: {fpath.name}")
            else:
                logger.warning(f"  上传返回错误: {data.get('message')}")
        else:
            logger.warning(f"  上传失败 (HTTP {resp.status_code}): {resp.text[:200]}")

    return uploaded_ids


def trigger_parsing(client: httpx.Client, dataset_id: str, document_ids: list):
    """触发文档异步解析"""
    if not document_ids:
        logger.info("无新文档需要解析")
        return

    logger.info(f"触发 {len(document_ids)} 个文档的异步解析...")

    payload = {"document_ids": document_ids}
    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/chunks",
        json=payload,
    )

    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            logger.info("异步解析已触发，文档将在后台处理")
        else:
            logger.warning(f"触发解析返回错误: {data.get('message')}")
    else:
        logger.warning(f"触发解析失败 (HTTP {resp.status_code})")

    # 等待一小段时间并检查解析状态
    logger.info("等待 5 秒后检查解析状态...")
    time.sleep(5)

    resp = client.get(
        f"/api/v1/datasets/{dataset_id}/documents",
        params={"page": 1, "page_size": 100},
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("code") == 0:
            docs = data.get("data", {}).get("docs", [])
            for doc in docs:
                name = doc.get("name", "")
                status = doc.get("run", "")
                chunk_num = doc.get("chunk_num", 0)
                logger.info(f"  {name}: 状态={status}, 分块数={chunk_num}")


def main():
    logger.info("=" * 60)
    logger.info("RAGFlow 知识库初始化脚本")
    logger.info("=" * 60)

    api_key, base_url = get_config()
    logger.info(f"RAGFlow 地址: {base_url}")

    client = create_client(api_key, base_url)

    # 1. 创建/获取数据集
    dataset_id = find_or_create_dataset(client)

    # 2. 上传文档
    new_doc_ids = upload_documents(client, dataset_id)

    # 3. 触发解析
    trigger_parsing(client, dataset_id, new_doc_ids)

    # 4. 输出配置
    logger.info("")
    logger.info("=" * 60)
    logger.info("初始化完成！请将以下配置添加到 .env 文件:")
    logger.info(f"  RAGFLOW_DATASET_IDS={dataset_id}")
    logger.info("=" * 60)

    client.close()


if __name__ == "__main__":
    main()
