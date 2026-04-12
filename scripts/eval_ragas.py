"""
RAGAS 评估脚本 — 粮储 RAG 系统质量评估

评估维度:
  - Faithfulness:       回答是否忠实于检索到的上下文
  - Answer Relevancy:   回答与问题的相关性
  - Context Precision:  检索上下文中相关片段的排序质量
  - Context Recall:     检索上下文对 ground_truth 的覆盖程度

使用方式:
  cd v008
  python -m scripts.eval_ragas
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 确保项目根目录在 sys.path 中，以便 import app.*
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ======================================================================
# 1. 加载测试集
# ======================================================================

def load_testset(path: Path) -> list[dict]:
    """加载 data/eval/testset.json"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"已加载测试集: {len(data)} 条样本")
    return data


# ======================================================================
# 2. 检索 + 生成
# ======================================================================

def retrieve_contexts(question: str) -> list[str]:
    """调用 RAGService.search() 获取检索上下文"""
    from app.services.rag_service import get_rag_service

    rag = get_rag_service()
    result = rag.search(question, top_k=settings.RAG_TOP_K)

    if result.get("status") != "success":
        logger.warning(f"检索失败: {result.get('message', 'unknown')}")
        return []

    contexts = [r["content"] for r in result.get("results", []) if r.get("content")]
    return contexts


def generate_answer(question: str, contexts: list[str]) -> str:
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
        timeout=30.0,
    )

    return response.choices[0].message.content or ""


# ======================================================================
# 3. RAGAS 评估
# ======================================================================

def build_ragas_dataset(samples: list[dict]) -> list[dict]:
    """对每个样本执行检索+生成，组装为 RAGAS 所需的 dataset"""
    eval_samples = []

    for i, sample in enumerate(samples):
        question = sample["question"]
        ground_truth = sample["ground_truth"]

        logger.info(f"[{i+1}/{len(samples)}] 处理: {question[:40]}...")

        # 检索
        contexts = retrieve_contexts(question)
        if not contexts:
            logger.warning(f"  -> 未检索到上下文，使用空列表")

        # 生成
        answer = generate_answer(question, contexts)
        logger.info(f"  -> 检索到 {len(contexts)} 个片段, 生成回答 {len(answer)} 字")

        eval_samples.append({
            "user_input": question,
            "response": answer,
            "retrieved_contexts": contexts,
            "reference": ground_truth,
        })

    return eval_samples


def run_ragas_evaluation(eval_samples: list[dict]) -> dict:
    """
    使用 RAGAS 框架计算四个核心指标。

    RAGAS v0.2+ API:
      - 使用 EvaluationDataset / SingleTurnSample
      - 通过 LangchainLLMWrapper / LangchainEmbeddingsWrapper 适配 judge 模型
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

    # ---- Judge LLM（复用通义千问 OpenAI 兼容接口）----
    judge_llm = LangchainLLMWrapper(
        ChatOpenAI(
            model=settings.LLM_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=0.1,
        )
    )

    # ---- Judge Embedding ----
    # check_embedding_ctx_length=False: 禁用 tiktoken 分词，直接发送原始文本
    # 通义千问 Embedding 接口只接受字符串，不接受 token ID 数组
    judge_embeddings = LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.EMBEDDING_API_KEY or settings.DASHSCOPE_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
            dimensions=settings.EMBEDDING_DIMENSIONS,
            check_embedding_ctx_length=False,
        )
    )

    # ---- 构建 EvaluationDataset ----
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

    # ---- 定义指标 ----
    metrics = [
        Faithfulness(),
        ResponseRelevancy(),
        LLMContextPrecisionWithoutReference(),
        LLMContextRecall(),
    ]

    # ---- 执行评估 ----
    logger.info("开始 RAGAS 评估（可能需要几分钟）...")
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=judge_llm,
        embeddings=judge_embeddings,
    )

    return result


# ======================================================================
# 4. 结果输出
# ======================================================================

def print_results(result) -> dict:
    """打印评估结果到终端，并返回可序列化的字典"""

    # RAGAS 0.4.x: EvaluationResult 对象
    # - result.to_pandas() → DataFrame（逐样本分数）
    # - result.total_scores() → dict（各指标平均分）（0.4.x 新 API）
    # - 兼容旧版: 尝试 dict(result) 或 result._repr_dict

    # 指标名称映射（便于阅读）
    metric_display = {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "response_relevancy": "Answer Relevancy",
        "llm_context_precision_without_reference": "Context Precision",
        "context_precision": "Context Precision",
        "llm_context_recall": "Context Recall",
        "context_recall": "Context Recall",
    }

    # ---- 提取总体平均分 ----
    scores_dict = {}
    try:
        # RAGAS 0.4.x 推荐方式
        scores_dict = result.total_scores()
    except (AttributeError, TypeError):
        pass

    if not scores_dict:
        try:
            # 兼容: 从 DataFrame 计算平均
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
            logger.warning(f"无法提取评估分数，result 类型: {type(result)}, 属性: {dir(result)}")

    print("\n" + "=" * 50)
    print("  RAGAS 评估结果 — 粮储 RAG 系统")
    print("=" * 50)

    summary = {}
    for key, value in scores_dict.items():
        if isinstance(value, (int, float)):
            display_name = metric_display.get(key, key)
            summary[display_name] = round(value, 4)
            print(f"  {display_name:<25s} {value:.4f}")

    print("=" * 50 + "\n")

    # ---- 逐样本结果 ----
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

    return {
        "summary": summary,
        "per_sample": per_sample,
        "timestamp": datetime.now().isoformat(),
    }


def save_results(results_dict: dict, path: Path):
    """保存评估结果到 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results_dict, f, ensure_ascii=False, indent=2)
    logger.info(f"评估结果已保存到: {path}")


# ======================================================================
# main
# ======================================================================

def main():
    testset_path = BASE_DIR / "data" / "eval" / "testset.json"
    results_path = BASE_DIR / "data" / "eval" / "results.json"

    if not testset_path.exists():
        logger.error(f"测试集文件不存在: {testset_path}")
        sys.exit(1)

    # 1. 加载测试集
    samples = load_testset(testset_path)

    # 2. 检索 + 生成
    eval_samples = build_ragas_dataset(samples)

    # 3. RAGAS 评估
    result = run_ragas_evaluation(eval_samples)

    # 4. 输出结果
    results_dict = print_results(result)
    save_results(results_dict, results_path)

    print(f"完成! 详细结果已保存到 {results_path}")


if __name__ == "__main__":
    main()
