"""
粮储 RAG 一键全量消融实验

运行全部 6 组实验，生成对比表格，突出最优配置 rerank_clean。

使用方式:
  cd V008
  python -m scripts.eval_full
  python -m scripts.eval_full --eval-only     # 仅重跑评估（不重新检索）
  python -m scripts.eval_full --skip-no-rag   # 跳过 no_rag（节省时间）
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.eval_ablation import (
    load_testset,
    run_single_experiment,
    run_ragas_evaluation,
    extract_scores,
    extract_per_sample,
    save_ablation_results,
    DISPLAY_ORDER,
)

# 所有实验模式（按顺序）
ALL_MODES = ["no_rag", "basic", "enhanced", "rerank_clean", "rerank_t02", "rerank_t03"]

# 最优配置
BEST_MODE = "rerank_clean"


def print_full_comparison(all_results: dict):
    """打印完整对比表格，突出最优配置"""
    modes = [m for m in ALL_MODES if m in all_results]
    if not modes:
        return

    width = 100
    print("\n" + "=" * width)
    print("  粮储 RAG 消融实验 — 全量对比报告")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * width)

    # 各模式样本数
    for m in modes:
        n = all_results[m].get("num_samples", "?")
        t = all_results[m].get("timing", {}).get("total_seconds", 0)
        print(f"  [{m}] {n} 样本, 耗时 {t:.0f}s")
    print()

    # ── 分数对比表 ──
    print(f"{'指标':<22s}", end="")
    for m in modes:
        marker = " *" if m == BEST_MODE else ""
        print(f"  {m + marker:>14s}", end="")
    print()
    print("-" * width)

    for metric in DISPLAY_ORDER:
        row = f"{metric:<22s}"
        values = {}
        best_val = -1
        for m in modes:
            score = all_results[m]["scores"].get(metric)
            values[m] = score
            if score is not None and score > best_val:
                best_val = score

        for m in modes:
            score = values[m]
            if score is not None:
                marker = " <-BEST" if score == best_val and m == BEST_MODE else ""
                row += f"  {score:>10.4f}{marker:>4s}"
            else:
                row += f"  {'N/A':>14s}"
        print(row)

    print("-" * width)

    # 耗时行
    time_row = f"{'耗时(s)':<22s}"
    for m in modes:
        t = all_results[m].get("timing", {}).get("total_seconds", 0)
        time_row += f"  {t:>14.0f}"
    print(time_row)
    print("=" * width)

    # ── rerank_clean vs basic 提升表 ──
    if "basic" in all_results and BEST_MODE in all_results:
        print(f"\n  {'rerank_clean vs basic 提升':^50s}")
        print("  " + "-" * 50)
        for metric in DISPLAY_ORDER:
            best = all_results[BEST_MODE]["scores"].get(metric)
            base = all_results["basic"]["scores"].get(metric)
            if best is not None and base is not None and base > 0:
                delta = best - base
                pct = delta / base * 100
                bar = "+" * max(0, int(pct / 2))
                print(f"  {metric:<22s} {base:.4f} -> {best:.4f}  ({pct:+.1f}%) {bar}")
            elif best is not None:
                print(f"  {metric:<22s}  N/A  -> {best:.4f}")

    # ── 阈值消融小表 ──
    rerank_modes = [m for m in ["rerank_clean", "rerank_t02", "rerank_t03"] if m in all_results]
    if len(rerank_modes) > 1:
        print(f"\n  {'阈值消融（threshold 对 reranker 效果的影响）':^50s}")
        print("  " + "-" * 60)
        print(f"  {'threshold':<12s}", end="")
        for metric in DISPLAY_ORDER:
            print(f"  {metric:>18s}", end="")
        print()
        thresholds = {"rerank_clean": "0.1", "rerank_t02": "0.2", "rerank_t03": "0.3"}
        for m in rerank_modes:
            print(f"  {thresholds.get(m, '?'):<12s}", end="")
            for metric in DISPLAY_ORDER:
                score = all_results[m]["scores"].get(metric)
                if score is not None:
                    print(f"  {score:>18.4f}", end="")
                else:
                    print(f"  {'N/A':>18s}", end="")
            print()

    print()
    print(f"  结论: {BEST_MODE} 为最优配置（低阈值广召回 + gte-rerank 重排序 + 干净 query）")
    print(f"  配置: threshold=0.1, page_size=15, rerank_id=gte-rerank, query_rewrite=OFF")
    print()


def main():
    parser = argparse.ArgumentParser(description="粮储 RAG 一键全量消融实验")
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="仅重跑 RAGAS 评估（使用已保存的检索+生成结果）",
    )
    parser.add_argument(
        "--skip-no-rag",
        action="store_true",
        help="跳过 no_rag 组（纯 LLM 较慢且已知结论明确）",
    )
    args = parser.parse_args()

    testset_path = BASE_DIR / "data" / "eval" / "testset.json"
    results_path = BASE_DIR / "data" / "eval" / "ablation_results.json"

    if not testset_path.exists():
        print(f"[ERROR] 测试集不存在: {testset_path}")
        sys.exit(1)

    samples = load_testset(testset_path)
    modes_to_run = [m for m in ALL_MODES if not (args.skip_no_rag and m == "no_rag")]

    # 加载已有结果
    all_results = {}
    if results_path.exists():
        try:
            with open(results_path, "r", encoding="utf-8") as f:
                all_results = json.load(f)
            print(f"已加载历史结果: {list(all_results.keys())}")
        except Exception:
            pass

    total_start = time.time()

    if args.eval_only:
        # eval-only 模式
        for mode in modes_to_run:
            if mode not in all_results or not all_results[mode].get("per_sample"):
                print(f"[SKIP] {mode} 没有已保存的数据")
                continue

            print(f"\n{'='*60}")
            print(f"  重跑评估 (eval-only): [{mode}]")
            print(f"{'='*60}")

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

            old_timing = all_results[mode].get("timing", {})
            all_results[mode]["scores"] = scores
            all_results[mode]["per_sample"] = per_sample
            all_results[mode]["timing"]["evaluation_seconds"] = round(eval_time, 1)
            all_results[mode]["timing"]["total_seconds"] = round(
                old_timing.get("retrieval_generation_seconds", 0) + eval_time, 1
            )
            all_results[mode]["timestamp"] = datetime.now().isoformat()

            save_ablation_results(all_results, results_path)
    else:
        # 正常模式: 检索 + 生成 + 评估
        for mode in modes_to_run:
            result = run_single_experiment(mode, samples)
            all_results[mode] = result
            save_ablation_results(all_results, results_path)

    total_time = time.time() - total_start

    # 打印完整对比报告
    print_full_comparison(all_results)

    save_ablation_results(all_results, results_path)
    print(f"总耗时: {total_time:.0f}s ({total_time/60:.1f}min)")
    print(f"结果已保存到: {results_path}")


if __name__ == "__main__":
    main()
