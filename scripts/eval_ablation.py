"""
粮储 RAG 消融实验脚本

三组实验对比:
  - no_rag:    纯 LLM，不检索任何知识
  - basic:     RAGFlow 默认配置（关闭查询改写，默认参数）
  - enhanced:  关键词注入 + RAGFlow 原生 Reranker (gte-rerank) + 参数调优

评估指标 (RAGAS):
  - Faithfulness / Answer Relevancy / Context Precision / Context Recall

使用方式:
  cd V008
  python -m scripts.eval_ablation --mode all
  python -m scripts.eval_ablation --mode no_rag
  python -m scripts.eval_ablation --mode basic
  python -m scripts.eval_ablation --mode enhanced
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ======================================================================
# 1. 测试集加载
# ======================================================================

def load_testset(path: Path) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"已加载测试集: {len(data)} 条样本")
    return data


# ======================================================================
# 2. RAGFlow 底层检索（直接调 HTTP API）
# ======================================================================

def _get_ragflow_client():
    """创建 RAGFlow httpx 客户端"""
    import httpx
    return httpx.Client(
        base_url=settings.RAGFLOW_BASE_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.RAGFLOW_API_KEY}",
        },
        timeout=60.0,
    )


def _get_dataset_ids() -> List[str]:
    return [
        ds_id.strip()
        for ds_id in settings.RAGFLOW_DATASET_IDS.split(",")
        if ds_id.strip()
    ]


def _call_ragflow_retrieval(
    client,
    question: str,
    similarity_threshold: float = 0.3,
    vector_similarity_weight: float = 0.3,
    page_size: int = 5,
    rerank_id: str = None,
) -> List[Dict[str, Any]]:
    """调用 RAGFlow /api/v1/retrieval，返回 chunk 列表"""
    dataset_ids = _get_dataset_ids()
    payload: Dict[str, Any] = {
        "question": question,
        "similarity_threshold": similarity_threshold,
        "vector_similarity_weight": vector_similarity_weight,
        "top_k": 1024,
        "page": 1,
        "page_size": page_size,
    }
    if dataset_ids:
        payload["dataset_ids"] = dataset_ids
    if rerank_id:
        payload["rerank_id"] = rerank_id

    try:
        resp = client.post("/api/v1/retrieval", json=payload)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("chunks", [])
            else:
                logger.warning(f"RAGFlow 返回错误: {data.get('message')}")
        else:
            logger.warning(f"RAGFlow HTTP 错误: {resp.status_code}")
    except Exception as e:
        logger.warning(f"RAGFlow 请求失败: {e}")
    return []


def _chunks_to_contexts(chunks: List[Dict[str, Any]]) -> List[str]:
    """从 RAGFlow chunk 列表提取 content 文本"""
    return [c.get("content", "").strip() for c in chunks if c.get("content", "").strip()]


# ======================================================================
# 3. 三组检索策略
# ======================================================================

# ---------- no_rag ----------

def retrieve_no_rag(question: str) -> List[str]:
    """纯 LLM，不检索"""
    return []


# ---------- basic ----------

def retrieve_basic(question: str, client) -> List[str]:
    """
    基础 RAG: 原始 query 直接调 RAGFlow，默认参数。
    关闭查询改写，不做任何增强。
    """
    chunks = _call_ragflow_retrieval(
        client,
        question=question,
        similarity_threshold=0.3,
        vector_similarity_weight=0.3,
        page_size=5,
    )
    contexts = _chunks_to_contexts(chunks)
    logger.info(f"  [basic] 检索到 {len(contexts)} 个片段")
    return contexts


# ---------- enhanced: 5 策略组合 ----------

# 策略 4: 领域关键词注入
DOMAIN_SYNONYMS = {
    "温度": ["粮温", "仓温", "粮堆温度"],
    "害虫": ["储粮害虫", "虫粮等级", "害虫密度"],
    "水分": ["安全水分", "粮食水分", "含水量"],
    "通风": ["机械通风", "自然通风", "通风降温"],
    "熏蒸": ["磷化铝熏蒸", "环流熏蒸", "熏蒸杀虫"],
    "气调": ["气调储藏", "充氮气调", "二氧化碳气调"],
    "密封": ["粮堆密封", "仓房密封", "气密性"],
    "虫": ["储粮害虫", "虫粮等级", "害虫密度"],
    "仓": ["粮仓", "仓房", "高大平房仓"],
    "检测": ["粮情检测", "温度检测", "害虫检测"],
    "储藏": ["粮油储藏", "储粮技术", "安全储藏"],
    "安全": ["储藏安全", "安全生产", "安全水分"],
}

STANDARD_MAPPINGS = {
    "储藏": "GB/T 29890",
    "储藏技术": "LST 1211-2008",
    "通风": "LS/T 1202",
    "安全操作": "LS 1206-2005",
    "熏蒸": "GB/T 25229",
    "害虫": "GB/T 29890",
    "气调": "LST 1211-2008",
    "仓库": "LS 1206-2005",
    "检测": "LST 1211-2008",
    "水分": "GB/T 29890",
}


def inject_domain_keywords(query: str) -> str:
    """策略4: 粮储同义词 + 标准编号注入"""
    injected_terms = []

    # 同义词注入
    for keyword, synonyms in DOMAIN_SYNONYMS.items():
        if keyword in query:
            for syn in synonyms:
                if syn not in query and syn not in injected_terms:
                    injected_terms.append(syn)
                    if len(injected_terms) >= 3:
                        break
        if len(injected_terms) >= 3:
            break

    # 标准编号注入
    for keyword, standard in STANDARD_MAPPINGS.items():
        if keyword in query and standard not in query and standard not in injected_terms:
            injected_terms.append(standard)
            if len(injected_terms) >= 5:
                break

    if injected_terms:
        enhanced_query = query + " " + " ".join(injected_terms)
        logger.info(f"  [enhanced] 关键词注入: +{injected_terms}")
        return enhanced_query
    return query



def retrieve_enhanced(question: str, client) -> List[str]:
    """
    增强 RAG: 关键词注入 + RAGFlow 原生 Reranker + 参数调优
      策略1: 领域关键词注入 — 补充同义词和标准编号，提升 query 质量
      策略2: RAGFlow gte-rerank — 用专业重排序模型替代纯向量排序
      策略3: 广召回 + 宽阈值 — page_size=10, threshold=0.1 多拿候选给 reranker 筛
    """
    # 策略1: 关键词注入
    enriched_query = inject_domain_keywords(question)
    logger.info(f"  [enhanced] 检索 query: {enriched_query[:60]}...")

    # 策略2+3: 单条 query → RAGFlow 广召回 + gte-rerank 重排序
    chunks = _call_ragflow_retrieval(
        client,
        question=enriched_query,
        similarity_threshold=0.1,        # 宽松阈值，reranker 分数尺度不同，需要放宽
        vector_similarity_weight=0.3,    # 混合权重与 basic 相同
        page_size=10,                    # 广召回: 多拿候选给 reranker 精选
        rerank_id="gte-rerank",          # 策略2: RAGFlow 原生 reranker
    )
    logger.info(f"  [enhanced] RAGFlow+rerank 返回 {len(chunks)} 个 chunk")

    if not chunks:
        return []

    # 取 top 5（与 basic 对齐），reranker 已经做好排序
    top_chunks = chunks[:5]

    for i, c in enumerate(top_chunks):
        sim = c.get("similarity", 0.0)
        logger.info(f"    #{i+1} sim={sim:.3f} | {c.get('content', '')[:50]}...")

    contexts = _chunks_to_contexts(top_chunks)
    logger.info(f"  [enhanced] 最终返回 {len(contexts)} 个上下文片段")
    return contexts


# ---------- rerank 系列: 干净 query + reranker + 不同阈值 ----------

def _retrieve_rerank(question: str, client, threshold: float, page_size: int, label: str) -> List[str]:
    """干净 query + 广召回 + gte-rerank，参数化阈值"""
    chunks = _call_ragflow_retrieval(
        client,
        question=question,
        similarity_threshold=threshold,
        vector_similarity_weight=0.3,
        page_size=page_size,
        rerank_id="gte-rerank",
    )
    logger.info(f"  [{label}] RAGFlow+rerank 返回 {len(chunks)} 个 chunk (threshold={threshold})")

    if not chunks:
        return []

    top_chunks = chunks[:5]

    for i, c in enumerate(top_chunks):
        sim = c.get("similarity", 0.0)
        logger.info(f"    #{i+1} sim={sim:.3f} | {c.get('content', '')[:50]}...")

    contexts = _chunks_to_contexts(top_chunks)
    logger.info(f"  [{label}] 最终返回 {len(contexts)} 个上下文片段")
    return contexts


def retrieve_rerank_clean(question: str, client) -> List[str]:
    """threshold=0.1, page_size=15"""
    return _retrieve_rerank(question, client, threshold=0.1, page_size=15, label="rerank_clean")


def retrieve_rerank_t02(question: str, client) -> List[str]:
    """threshold=0.2, page_size=15"""
    return _retrieve_rerank(question, client, threshold=0.2, page_size=15, label="rerank_t02")


def retrieve_rerank_t03(question: str, client) -> List[str]:
    """threshold=0.3, page_size=15"""
    return _retrieve_rerank(question, client, threshold=0.3, page_size=15, label="rerank_t03")


# ======================================================================
# 4. LLM 回答生成
# ======================================================================

def generate_answer(question: str, contexts: List[str]) -> str:
    """基于检索上下文，调用 LLM 生成回答"""
    from openai import OpenAI

    client = OpenAI(
        api_key=settings.DASHSCOPE_API_KEY,
        base_url=settings.LLM_BASE_URL,
    )

    context_text = "\n\n---\n\n".join(contexts) if contexts else "（未检索到相关知识）"

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的粮食储藏技术顾问。请严格基于下方提供的参考资料回答用户问题。"
                "如果参考资料不足以回答，请明确说明。不要编造信息。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"参考资料:\n{context_text}\n\n"
                f"问题: {question}\n\n"
                "请给出准确、简洁的回答:"
            ),
        },
    ]

    response = client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        temperature=0.1,
        timeout=120.0,
    )

    return response.choices[0].message.content or ""


# ======================================================================
# 5. RAGAS 评估
# ======================================================================

def run_ragas_evaluation(eval_samples: List[dict], mode: str) -> dict:
    """
    使用 RAGAS 框架评估。

    no_rag 模式下 contexts 为空，仅评估 Faithfulness + Answer Relevancy。
    basic / enhanced 模式评估全部四个指标。
    """
    from ragas import evaluate, EvaluationDataset, SingleTurnSample
    from ragas.metrics import (
        Faithfulness,
        ResponseRelevancy,
        LLMContextPrecisionWithoutReference,
        LLMContextRecall,
    )
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    # Judge LLM
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0.1,
        )
    )

    # Judge Embedding
    judge_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.EMBEDDING_API_KEY or settings.DASHSCOPE_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
            check_embedding_ctx_length=False,
        )
    )

    # 构建 dataset
    ragas_samples = []
    for s in eval_samples:
        ragas_samples.append(
            SingleTurnSample(
                user_input=s["user_input"],
                response=s["response"],
                retrieved_contexts=s["retrieved_contexts"],
                reference=s["reference"],
            )
        )
    dataset = EvaluationDataset(samples=ragas_samples)

    # 指标选择
    if mode == "no_rag":
        # contexts 为空，Context Precision / Recall 无意义
        metrics = [
            Faithfulness(),
            ResponseRelevancy(),
        ]
    else:
        metrics = [
            Faithfulness(),
            ResponseRelevancy(),
            LLMContextPrecisionWithoutReference(),
            LLMContextRecall(),
        ]

    logger.info(f"开始 RAGAS 评估 [{mode}]（可能需要几分钟）...")
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    return result


# ======================================================================
# 6. 结果提取与格式化
# ======================================================================

# 指标名称映射
METRIC_DISPLAY = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "response_relevancy": "Answer Relevancy",
    "llm_context_precision_without_reference": "Context Precision",
    "context_precision": "Context Precision",
    "llm_context_recall": "Context Recall",
    "context_recall": "Context Recall",
}

# 统一显示顺序
DISPLAY_ORDER = ["Faithfulness", "Answer Relevancy", "Context Precision", "Context Recall"]


def extract_scores(result) -> Dict[str, float]:
    """从 RAGAS 结果对象提取平均分"""
    scores_dict = {}
    try:
        scores_dict = result.total_scores()
    except (AttributeError, TypeError):
        pass

    if not scores_dict:
        try:
            df = result.to_pandas()
            for col in df.columns:
                if df[col].dtype in ("float64", "float32", "int64"):
                    scores_dict[col] = float(df[col].mean())
        except Exception:
            pass

    if not scores_dict:
        try:
            scores_dict = dict(result)
        except Exception:
            logger.warning(f"无法提取评估分数")

    # 映射为统一显示名
    mapped = {}
    for key, value in scores_dict.items():
        if isinstance(value, (int, float)):
            display_name = METRIC_DISPLAY.get(key, key)
            mapped[display_name] = round(value, 4)

    return mapped


def extract_per_sample(result) -> List[dict]:
    """提取逐样本结果"""
    per_sample = []
    try:
        df = result.to_pandas()
        for _, row in df.iterrows():
            sample_result = {}
            for col in df.columns:
                val = row[col]
                if isinstance(val, float):
                    sample_result[col] = round(val, 4)
                elif isinstance(val, list):
                    sample_result[col] = val
                else:
                    sample_result[col] = str(val) if val is not None else None
            per_sample.append(sample_result)
    except Exception as e:
        logger.warning(f"无法导出逐样本结果: {e}")
    return per_sample


# ======================================================================
# 7. 单组实验运行
# ======================================================================

def run_single_experiment(mode: str, samples: List[dict]) -> Dict[str, Any]:
    """运行单组实验: 检索 → 生成 → 评估"""
    logger.info(f"\n{'='*60}")
    logger.info(f"  开始实验: [{mode}]")
    logger.info(f"{'='*60}")

    ragflow_client = None
    if mode in ("basic", "enhanced", "rerank_clean", "rerank_t02", "rerank_t03"):
        ragflow_client = _get_ragflow_client()

    eval_samples = []
    start_time = time.time()

    for i, sample in enumerate(samples):
        question = sample["question"]
        ground_truth = sample["ground_truth"]
        logger.info(f"[{i+1}/{len(samples)}] {question[:50]}...")

        # 检索
        if mode == "no_rag":
            contexts = retrieve_no_rag(question)
        elif mode == "basic":
            contexts = retrieve_basic(question, ragflow_client)
        elif mode == "enhanced":
            contexts = retrieve_enhanced(question, ragflow_client)
        elif mode == "rerank_clean":
            contexts = retrieve_rerank_clean(question, ragflow_client)
        elif mode == "rerank_t02":
            contexts = retrieve_rerank_t02(question, ragflow_client)
        elif mode == "rerank_t03":
            contexts = retrieve_rerank_t03(question, ragflow_client)
        else:
            raise ValueError(f"未知模式: {mode}")

        # 生成
        answer = generate_answer(question, contexts)
        logger.info(f"  -> contexts={len(contexts)}, answer={len(answer)}字")

        eval_samples.append({
            "user_input": question,
            "response": answer,
            "retrieved_contexts": contexts,
            "reference": ground_truth,
        })

    retrieval_gen_time = time.time() - start_time
    logger.info(f"[{mode}] 检索+生成完成，耗时 {retrieval_gen_time:.1f}s")

    # RAGAS 评估
    eval_start = time.time()
    result = run_ragas_evaluation(eval_samples, mode)
    eval_time = time.time() - eval_start

    scores = extract_scores(result)
    per_sample = extract_per_sample(result)

    total_time = time.time() - start_time

    if ragflow_client:
        ragflow_client.close()

    return {
        "mode": mode,
        "scores": scores,
        "per_sample": per_sample,
        "timing": {
            "retrieval_generation_seconds": round(retrieval_gen_time, 1),
            "evaluation_seconds": round(eval_time, 1),
            "total_seconds": round(total_time, 1),
        },
        "num_samples": len(samples),
        "timestamp": datetime.now().isoformat(),
    }


# ======================================================================
# 8. 对比表格输出
# ======================================================================

def print_comparison_table(all_results: Dict[str, Dict[str, Any]]):
    """打印各组实验的对比表格 + 提升百分比"""
    modes = [m for m in ("no_rag", "basic", "enhanced", "rerank_clean", "rerank_t02", "rerank_t03") if m in all_results]

    if not modes:
        return

    width = 90
    print("\n" + "=" * width)
    print("  消融实验结果对比 — 粮储 RAG 系统")
    print("=" * width)

    # 表头
    header = f"{'指标':<22s}"
    for m in modes:
        header += f"  {m:>12s}"
    # 提升列: 各模式 vs basic
    for m in modes:
        if m != "basic" and m != "no_rag" and "basic" in all_results:
            header += f"  {m[:6]+'↑':>10s}"
    print(header)
    print("-" * width)

    for metric in DISPLAY_ORDER:
        row = f"{metric:<22s}"
        values = {}
        for m in modes:
            score = all_results[m]["scores"].get(metric)
            values[m] = score
            if score is not None:
                row += f"  {score:>12.4f}"
            else:
                row += f"  {'N/A':>12s}"

        # 各模式 vs basic 的提升
        for m in modes:
            if m != "basic" and m != "no_rag" and "basic" in all_results:
                val = values.get(m)
                base = values.get("basic")
                if val is not None and base is not None and base > 0:
                    pct = (val - base) / base * 100
                    row += f"  {pct:>+9.1f}%"
                else:
                    row += f"  {'--':>10s}"

        print(row)

    print("-" * width)

    # 耗时
    time_row = f"{'耗时(s)':<22s}"
    for m in modes:
        t = all_results[m]["timing"]["total_seconds"]
        time_row += f"  {t:>12.1f}"
    print(time_row)

    print("=" * width)

    # 说明
    if "no_rag" in all_results:
        print("  注: no_rag 的 Context Precision / Context Recall 为 N/A（无检索上下文）")
    if "rerank_clean" in all_results:
        print("  注: rerank_clean = 干净 query + 广召回(15) + gte-rerank，隔离验证 reranker 效果")
    print()


# ======================================================================
# 9. 结果保存
# ======================================================================

def save_ablation_results(all_results: Dict[str, Dict[str, Any]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    logger.info(f"消融实验结果已保存到: {path}")


# ======================================================================
# main
# ======================================================================

def main():
    parser = argparse.ArgumentParser(description="粮储 RAG 消融实验")
    parser.add_argument(
        "--mode",
        choices=["no_rag", "basic", "enhanced", "rerank_clean", "rerank_t02", "rerank_t03", "all"],
        default="all",
        help="实验模式: no_rag / basic / enhanced / rerank_clean / rerank_t02 / rerank_t03 / all",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="仅重跑 RAGAS 评估（使用已保存的检索+生成结果，不重新检索）",
    )
    args = parser.parse_args()

    testset_path = BASE_DIR / "data" / "eval" / "testset.json"
    results_path = BASE_DIR / "data" / "eval" / "ablation_results.json"

    if not testset_path.exists():
        logger.error(f"测试集文件不存在: {testset_path}")
        sys.exit(1)

    samples = load_testset(testset_path)

    # 确定要运行的模式
    if args.mode == "all":
        modes_to_run = ["no_rag", "basic", "enhanced", "rerank_clean", "rerank_t02", "rerank_t03"]
    else:
        modes_to_run = [args.mode]

    # 加载已有结果（增量模式）
    all_results: Dict[str, Dict[str, Any]] = {}
    if results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                all_results = json.load(f)
            logger.info(f"已加载历史结果: {list(all_results.keys())}")
        except Exception:
            pass

    # --eval-only 模式: 用已保存的 per_sample 数据重跑 RAGAS 评估
    if args.eval_only:
        for mode in modes_to_run:
            if mode not in all_results or not all_results[mode].get("per_sample"):
                logger.error(f"[{mode}] 没有已保存的 per_sample 数据，无法 eval-only")
                continue

            logger.info(f"\n{'='*60}")
            logger.info(f"  重跑评估 (eval-only): [{mode}]")
            logger.info(f"{'='*60}")

            # 从已保存的 per_sample 中重建 eval_samples
            eval_samples = []
            for s in all_results[mode]["per_sample"]:
                eval_samples.append({
                    "user_input": s.get("user_input", ""),
                    "response": s.get("response", ""),
                    "retrieved_contexts": s.get("retrieved_contexts", []),
                    "reference": s.get("reference", ""),
                })

            eval_start = time.time()
            result = run_ragas_evaluation(eval_samples, mode)
            eval_time = time.time() - eval_start

            scores = extract_scores(result)
            per_sample = extract_per_sample(result)

            # 更新已有结果（保留原有 timing 的检索生成耗时）
            old_timing = all_results[mode].get("timing", {})
            all_results[mode]["scores"] = scores
            all_results[mode]["per_sample"] = per_sample
            all_results[mode]["timing"]["evaluation_seconds"] = round(eval_time, 1)
            all_results[mode]["timing"]["total_seconds"] = round(
                old_timing.get("retrieval_generation_seconds", 0) + eval_time, 1
            )
            all_results[mode]["timestamp"] = datetime.now().isoformat()

            print(f"\n--- [{mode}] 重新评估分数 ---")
            for metric in DISPLAY_ORDER:
                score = scores.get(metric)
                if score is not None:
                    print(f"  {metric:<22s} {score:.4f}")
                else:
                    print(f"  {metric:<22s} N/A")
            print(f"  评估耗时: {eval_time:.1f}s")

            save_ablation_results(all_results, results_path)

        if len(all_results) > 1:
            print_comparison_table(all_results)
        save_ablation_results(all_results, results_path)
        print(f"完成! 结果已保存到 {results_path}")
        return

    # 正常模式: 检索 → 生成 → 评估
    for mode in modes_to_run:
        result = run_single_experiment(mode, samples)

        # 打印单组结果
        print(f"\n--- [{mode}] 评估分数 ---")
        for metric in DISPLAY_ORDER:
            score = result["scores"].get(metric)
            if score is not None:
                print(f"  {metric:<22s} {score:.4f}")
            else:
                print(f"  {metric:<22s} N/A")
        print(f"  耗时: {result['timing']['total_seconds']:.1f}s")

        all_results[mode] = result

        # 每组跑完立刻保存（防止中断丢失）
        save_ablation_results(all_results, results_path)

    # 多组结果对比
    if len(all_results) > 1:
        print_comparison_table(all_results)

    save_ablation_results(all_results, results_path)
    print(f"完成! 结果已保存到 {results_path}")


if __name__ == "__main__":
    main()
