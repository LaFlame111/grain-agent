"""
RAG 知识检索服务（企业级 - RAGFlow + 增强层）

三层架构:
  1. 查询预处理层 — LLM 查询改写 + 多查询扩展 + 粮储领域关键词注入
  2. RAGFlow 检索层 — Hybrid Search (BM25 + 向量) + Reranker
  3. 后处理层       — 合并去重 + 置信度过滤 + 来源标注 + 上下文压缩

降级策略:
  - RAGFlow 不可用 → 回退到旧 ChromaDB 检索
  - 查询改写失败   → 使用原始 query 直接检索
  - 所有异常静默降级，不影响 Agent 主流程
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

import httpx

logger = logging.getLogger(__name__)


# ======================================================================
# 旧版 ChromaDB 检索（作为 fallback 保留）
# ======================================================================

class _ChromaFallback:
    """旧版 ChromaDB RAG，仅在 RAGFlow 不可用时作为降级方案"""

    def __init__(self):
        self._available = False
        self._collection = None
        self._embed_client = None
        self._try_init()

    def _try_init(self):
        try:
            from app.core.config import settings
            base_dir = Path(__file__).resolve().parent.parent.parent
            chroma_path = base_dir / "data" / "chroma_db"
            if not chroma_path.exists():
                return

            import chromadb
            client = chromadb.PersistentClient(path=str(chroma_path))
            try:
                self._collection = client.get_collection("grain_knowledge")
            except Exception:
                return
            if self._collection.count() == 0:
                return

            from openai import OpenAI
            self._embed_client = OpenAI(
                api_key=settings.EMBEDDING_API_KEY or settings.DASHSCOPE_API_KEY,
                base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
            )
            self._available = True
            logger.info(f"ChromaDB fallback 初始化成功，文档数: {self._collection.count()}")
        except Exception as e:
            logger.debug(f"ChromaDB fallback 初始化失败（非关键）: {e}")

    def search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        if not self._available:
            return {"status": "unavailable", "message": "ChromaDB fallback 不可用", "results": []}
        try:
            from app.core.config import settings
            resp = self._embed_client.embeddings.create(
                model=settings.EMBEDDING_MODEL,
                input=query,
                dimensions=settings.EMBEDDING_DIMENSIONS,
            )
            query_embedding = resp.data[0].embedding
            results = self._collection.query(query_embeddings=[query_embedding], n_results=min(top_k, 10))
            snippets = []
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            for doc, meta, dist in zip(documents, metadatas, distances):
                snippets.append({
                    "content": doc,
                    "source": meta.get("source", ""),
                    "title": meta.get("title", ""),
                    "relevance_score": round(1 - dist, 4),
                })
            return {"status": "success", "query": query, "total_results": len(snippets), "results": snippets}
        except Exception as e:
            return {"status": "error", "message": f"ChromaDB fallback 检索出错: {e}", "results": []}


# ======================================================================
# 主服务: RAGFlow + 增强层
# ======================================================================

class RAGService:
    """企业级 RAG 知识检索服务（RAGFlow + 查询增强）"""

    def __init__(self):
        from app.core.config import settings
        self._settings = settings

        # RAGFlow HTTP 客户端
        self._http_client: Optional[httpx.Client] = None
        self._ragflow_available = False

        # 查询改写 LLM 客户端
        self._rewrite_client = None
        self._rewrite_model: str = ""

        # ChromaDB 降级方案
        self._chroma_fallback: Optional[_ChromaFallback] = None

        self._initialize()

    # ------------------------------------------------------------------
    # 初始化
    # ------------------------------------------------------------------
    def _initialize(self):
        """初始化 RAGFlow 客户端与查询改写 LLM，任何失败均静默降级"""

        # 1) RAGFlow 连接
        if self._settings.RAGFLOW_API_KEY:
            try:
                self._http_client = httpx.Client(
                    base_url=self._settings.RAGFLOW_BASE_URL,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self._settings.RAGFLOW_API_KEY}",
                    },
                    timeout=30.0,
                )
                # 简单连通性检测
                resp = self._http_client.get("/api/v1/datasets", params={"page": 1, "page_size": 1})
                if resp.status_code == 200:
                    self._ragflow_available = True
                    logger.info(f"RAGFlow 连接成功: {self._settings.RAGFLOW_BASE_URL}")
                else:
                    logger.warning(f"RAGFlow 连通性检测失败 (HTTP {resp.status_code})")
            except Exception as e:
                logger.warning(f"RAGFlow 初始化失败: {e}，将尝试降级到 ChromaDB")
        else:
            logger.warning("RAGFLOW_API_KEY 未配置，RAGFlow 不可用")

        # 2) 查询改写 LLM 客户端（复用现有 DashScope 配置）
        if self._settings.RAG_ENABLE_QUERY_REWRITE and self._settings.DASHSCOPE_API_KEY:
            try:
                from openai import OpenAI
                self._rewrite_client = OpenAI(
                    api_key=self._settings.DASHSCOPE_API_KEY,
                    base_url=self._settings.LLM_BASE_URL,
                )
                self._rewrite_model = (
                    self._settings.RAG_QUERY_REWRITE_MODEL or self._settings.LLM_MODEL
                )
                logger.info(f"查询改写 LLM 已就绪，模型: {self._rewrite_model}")
            except Exception as e:
                logger.warning(f"查询改写 LLM 初始化失败: {e}，将跳过查询改写")

        # 3) ChromaDB 降级方案
        if not self._ragflow_available:
            self._chroma_fallback = _ChromaFallback()

    # ------------------------------------------------------------------
    # 公开属性
    # ------------------------------------------------------------------
    @property
    def is_available(self) -> bool:
        return self._ragflow_available or (
            self._chroma_fallback is not None and self._chroma_fallback._available
        )

    # ------------------------------------------------------------------
    # 核心入口: search()
    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        语义检索知识库（三层增强架构）

        接口签名和返回格式与旧版完全一致，对上层调用透明。

        Args:
            query: 查询文本
            top_k: 返回片段数量

        Returns:
            {
                "status": "success" | "error" | "unavailable",
                "query": str,
                "total_results": int,
                "results": [{"content", "source", "title", "relevance_score"}]
            }
        """
        # 降级: RAGFlow 不可用时走 ChromaDB
        if not self._ragflow_available:
            logger.info("RAGFlow 不可用，降级到 ChromaDB fallback")
            if self._chroma_fallback:
                return self._chroma_fallback.search(query, top_k)
            return {
                "status": "unavailable",
                "message": "RAGFlow 未连接且 ChromaDB fallback 不可用，知识检索服务不可用。",
                "results": [],
            }

        try:
            # ① 查询预处理层
            queries = self._preprocess_query(query)
            logger.info(f"查询预处理完成，共 {len(queries)} 个检索查询")

            # ② RAGFlow 检索层
            raw_chunks = self._retrieve_from_ragflow(queries, top_k)
            logger.info(f"RAGFlow 检索完成，共获取 {len(raw_chunks)} 个原始片段")

            # ③ 后处理层
            final_results = self._postprocess_results(raw_chunks, query, top_k)
            logger.info(f"后处理完成，最终返回 {len(final_results)} 个片段")

            return {
                "status": "success",
                "query": query,
                "total_results": len(final_results),
                "results": final_results,
            }

        except Exception as e:
            logger.error(f"RAGFlow 检索流程异常: {e}", exc_info=True)
            # 异常时尝试降级到 ChromaDB
            if self._chroma_fallback:
                logger.info("RAGFlow 检索异常，降级到 ChromaDB fallback")
                return self._chroma_fallback.search(query, top_k)
            return {
                "status": "error",
                "message": f"知识检索出错: {e}",
                "results": [],
            }

    # ==================================================================
    # 第 1 层: 查询预处理
    # ==================================================================
    def _preprocess_query(self, query: str) -> List[str]:
        """
        查询改写 + 多查询扩展

        将用户的原始 query 扩展为多个不同角度的检索查询，以提高召回率。
        如果 LLM 改写失败，降级为仅用原始 query。
        """
        # 始终包含原始查询
        queries = [query]

        if not self._settings.RAG_ENABLE_QUERY_REWRITE or not self._rewrite_client:
            return queries

        try:
            prompt = (
                "你是一个粮食储藏领域的知识检索助手。用户提出了一个问题，请你生成 2 个额外的检索查询，"
                "用于从粮储国家标准、操作规程、安全阈值等知识库中检索相关内容。\n\n"
                "要求：\n"
                "1. 第一个查询：提取问题中的核心概念，用更精确的专业术语重新表述\n"
                "2. 第二个查询：补充相关的标准编号或领域背景（如 GB/T 29890、LS/T 1202 等）\n"
                "3. 每个查询独占一行，不要编号，不要解释\n\n"
                f"用户问题：{query}\n\n"
                "请输出 2 个检索查询（每行一个）："
            )

            response = self._rewrite_client.chat.completions.create(
                model=self._rewrite_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                timeout=10.0,
            )

            content = response.choices[0].message.content or ""
            # 解析 LLM 输出的多行查询
            for line in content.strip().splitlines():
                line = line.strip().lstrip("0123456789.、-·）) ")
                if line and line != query and len(line) > 2:
                    queries.append(line)

            logger.info(f"查询改写成功: 原始 1 个 → 扩展为 {len(queries)} 个")

        except Exception as e:
            logger.warning(f"查询改写失败，使用原始 query: {e}")

        return queries[:4]  # 最多 4 个查询，防止过多

    # ==================================================================
    # 第 2 层: RAGFlow 检索
    # ==================================================================
    def _retrieve_from_ragflow(self, queries: List[str], top_k: int) -> List[Dict[str, Any]]:
        """
        对多个查询分别调用 RAGFlow 检索 API，返回所有原始 chunk。
        """
        all_chunks: List[Dict[str, Any]] = []

        dataset_ids = [
            ds_id.strip()
            for ds_id in self._settings.RAGFLOW_DATASET_IDS.split(",")
            if ds_id.strip()
        ]

        for q in queries:
            try:
                payload: Dict[str, Any] = {
                    "question": q,
                    "similarity_threshold": self._settings.RAG_SIMILARITY_THRESHOLD,
                    "vector_similarity_weight": 0.3,
                    "top_k": 1024,
                    "page": 1,
                    "page_size": self._settings.RAG_PAGE_SIZE,
                }

                if dataset_ids:
                    payload["dataset_ids"] = dataset_ids

                # rerank_clean: 使用 RAGFlow 原生 reranker
                if self._settings.RAG_RERANK_ID:
                    payload["rerank_id"] = self._settings.RAG_RERANK_ID

                resp = self._http_client.post("/api/v1/retrieval", json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        chunks = data.get("data", {}).get("chunks", [])
                        # 标记每个 chunk 来自哪个查询
                        for chunk in chunks:
                            chunk["_source_query"] = q
                        all_chunks.extend(chunks)
                    else:
                        logger.warning(f"RAGFlow 检索返回错误: code={data.get('code')}, msg={data.get('message')}")
                else:
                    logger.warning(f"RAGFlow HTTP 错误: {resp.status_code}")

            except Exception as e:
                logger.warning(f"RAGFlow 检索查询 '{q[:30]}...' 失败: {e}")

        return all_chunks

    # ==================================================================
    # 第 3 层: 后处理
    # ==================================================================
    def _postprocess_results(
        self, raw_chunks: List[Dict[str, Any]], original_query: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """
        合并去重 → 置信度过滤 → 排序截取 → 来源标注

        返回与旧版兼容的结果格式:
        [{"content", "source", "title", "relevance_score"}]
        """
        if not raw_chunks:
            return []

        # 1) 合并去重: 按 chunk id 去重，保留最高 similarity
        seen: Dict[str, Dict[str, Any]] = {}
        for chunk in raw_chunks:
            chunk_id = chunk.get("id", "")
            similarity = chunk.get("similarity", 0.0)
            if not chunk_id:
                # 没有 id 的 chunk 用 content hash 作为 key
                chunk_id = str(hash(chunk.get("content", "")))

            if chunk_id not in seen or similarity > seen[chunk_id].get("similarity", 0.0):
                seen[chunk_id] = chunk

        unique_chunks = list(seen.values())

        # 2) 置信度过滤
        threshold = self._settings.RAG_SIMILARITY_THRESHOLD
        filtered = [c for c in unique_chunks if c.get("similarity", 0.0) >= threshold]

        # 3) 按相似度降序排序
        filtered.sort(key=lambda c: c.get("similarity", 0.0), reverse=True)

        # 4) 截取 Top-K
        top_results = filtered[:top_k]

        # 5) 格式化输出（兼容旧版接口）
        results: List[Dict[str, Any]] = []
        for chunk in top_results:
            content = chunk.get("content", "").strip()
            # 来源标注
            doc_name = chunk.get("document_keyword", "") or chunk.get("document_name", "")
            source = doc_name or "RAGFlow 知识库"
            title = ""
            # 尝试从 important_keywords 中提取标题
            keywords = chunk.get("important_keywords", [])
            if keywords:
                title = "、".join(keywords[:3])

            results.append({
                "content": content,
                "source": source,
                "title": title,
                "relevance_score": round(chunk.get("similarity", 0.0), 4),
            })

        return results


# ======================================================================
# 单例
# ======================================================================
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取全局 RAGService 实例（单例）"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
