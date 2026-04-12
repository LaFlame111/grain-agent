# RAGAS 评估操作指南 — 粮储 RAG 系统

## 一、概述

RAGAS（Retrieval Augmented Generation Assessment）是一个用于量化评估 RAG 系统质量的开源框架。本项目通过 RAGAS 对粮储 RAG 系统进行四个维度的评估：

| 指标 | 含义 | 评估对象 |
|------|------|----------|
| **Faithfulness** | 回答是否忠实于检索到的上下文，不编造信息 | 生成质量 |
| **Answer Relevancy** | 回答与用户问题的相关程度 | 生成质量 |
| **Context Precision** | 检索结果中相关片段是否排在前面 | 检索质量 |
| **Context Recall** | 检索上下文对标准答案的覆盖程度 | 检索质量 |

所有指标得分范围为 **0 ~ 1**，越高越好。

---

## 二、文件结构

```
v008/
├── scripts/
│   └── eval_ragas.py          # 评估主脚本
├── data/
│   └── eval/
│       ├── testset.json       # 评估测试集（20 条 QA）
│       └── results.json       # 评估结果（运行后自动生成）
└── requirements.txt           # 已包含 ragas 依赖
```

---

## 三、环境准备

### 3.1 前置条件

- Python 3.10+
- `.env` 文件中已配置以下参数：
  - `DASHSCOPE_API_KEY` — 通义千问 API 密钥
  - `RAGFLOW_API_KEY` — RAGFlow API 密钥
  - `RAGFLOW_BASE_URL` — RAGFlow 服务地址
  - `RAGFLOW_DATASET_IDS` — RAGFlow 数据集 ID
- RAGFlow 服务正常运行（默认 `http://127.0.0.1:9380`）

### 3.2 安装依赖

```bash
pip install ragas datasets langchain-openai
```

或者通过 requirements.txt 一次性安装所有依赖：

```bash
pip install -r requirements.txt
```

> **注意**: `langchain-openai` 是 RAGAS 适配 judge 模型所必需的，需要单独安装（不在 requirements.txt 中，因为仅评估时使用）。

---

## 四、运行评估

### 4.1 基本运行

```bash
cd v008
python -m scripts.eval_ragas
```

### 4.2 运行过程

脚本会依次执行以下步骤：

1. **加载测试集** — 读取 `data/eval/testset.json`
2. **逐条处理**（20 条样本）：
   - 调用 `RAGService.search()` 检索相关文档片段
   - 调用通义千问 qwen-max 基于检索结果生成回答
3. **RAGAS 评估** — 使用通义千问作为 judge 模型计算四个指标
4. **输出结果** — 终端打印 + 保存到 `data/eval/results.json`

### 4.3 预计耗时

- 每条样本：检索 ~2s + 生成 ~3s
- RAGAS 评估（judge 模型打分）：~3-5 分钟
- **总计约 5-10 分钟**（取决于网络和 API 响应速度）

### 4.4 终端输出示例

```
2026-03-29 10:00:01 [INFO] 已加载测试集: 20 条样本
2026-03-29 10:00:01 [INFO] [1/20] 处理: 小麦的安全储存水分标准是多少？...
2026-03-29 10:00:03 [INFO]   -> 检索到 5 个片段, 生成回答 86 字
...
2026-03-29 10:03:00 [INFO] 开始 RAGAS 评估（可能需要几分钟）...

==================================================
  RAGAS 评估结果 — 粮储 RAG 系统
==================================================
  Faithfulness              0.8200
  Answer Relevancy          0.7800
  Context Precision         0.7500
  Context Recall            0.7100
==================================================

完成! 详细结果已保存到 data/eval/results.json
```

---

## 五、结果解读

### 5.1 总体评分参考

| 评分范围 | 质量判断 | 建议 |
|----------|----------|------|
| 0.85 ~ 1.0 | 优秀 | 系统表现良好，可投入使用 |
| 0.70 ~ 0.85 | 良好 | 基本可用，可针对性优化 |
| 0.50 ~ 0.70 | 一般 | 需要重点改进 |
| < 0.50 | 较差 | 系统存在明显缺陷，需排查 |

### 5.2 各指标偏低时的排查方向

| 指标偏低 | 可能原因 | 改进方向 |
|----------|----------|----------|
| Faithfulness 低 | LLM 编造了检索上下文中不存在的信息 | 调整 system prompt，强调"仅基于参考资料回答" |
| Answer Relevancy 低 | 回答偏题或过于冗长 | 优化生成 prompt，限制回答范围 |
| Context Precision 低 | 检索结果排序不佳，不相关内容排在前面 | 调高 `RAG_SIMILARITY_THRESHOLD`；优化 RAGFlow reranker |
| Context Recall 低 | 检索未能覆盖标准答案中的关键信息 | 增加 `RAG_TOP_K`；检查知识库文档是否完整入库；优化查询改写 |

### 5.3 结果文件 `results.json` 结构

```json
{
  "summary": {
    "Faithfulness": 0.82,
    "Answer Relevancy": 0.78,
    "Context Precision": 0.75,
    "Context Recall": 0.71
  },
  "per_sample": [
    {
      "user_input": "小麦的安全储存水分标准是多少？",
      "response": "根据 GB/T 29890-2013...",
      "faithfulness": 0.95,
      "response_relevancy": 0.88,
      ...
    }
  ],
  "timestamp": "2026-03-29T10:05:30.123456"
}
```

`per_sample` 包含每条样本的逐项得分，可用于定位具体哪些问题表现不佳。

---

## 六、自定义测试集

### 6.1 测试集格式

编辑 `data/eval/testset.json`，每条数据包含三个字段：

```json
{
  "question": "用户问题",
  "ground_truth": "标准答案（用于计算 Context Recall）",
  "metadata": {
    "source": "来源文档",
    "category": "知识类别"
  }
}
```

### 6.2 当前覆盖的知识类别

| 类别 | 数量 | 示例问题 |
|------|------|----------|
| temperature | 3 | 安全/警戒/危险温度阈值 |
| humidity | 3 | 小麦/稻谷/玉米安全水分 |
| gas | 3 | O2/PH3/CO2 浓度标准 |
| ventilation | 3 | 降温/均温/降水通风操作 |
| fumigation | 3 | 熏蒸准备/用药量/散气标准 |
| detection_frequency | 3 | 不同状态下的检测频次 |
| pest_control | 2 | 虫害等级与防治原则 |

### 6.3 添加新测试数据

向 `testset.json` 数组中追加新条目即可。建议：

- 每个类别至少 2-3 条，确保覆盖充分
- `ground_truth` 要具体、包含关键数值，便于评估召回率
- 可从新上传到 RAGFlow 的 PDF 文档中提取 QA 对

---

## 七、常见问题

### Q1: 报错 `ModuleNotFoundError: No module named 'ragas'`

```bash
pip install ragas datasets langchain-openai
```

### Q2: 报错 `RAGFlow 不可用，降级到 ChromaDB fallback`

检查 RAGFlow 服务是否启动：

```bash
curl http://127.0.0.1:9380/api/v1/datasets?page=1&page_size=1 \
  -H "Authorization: Bearer <你的RAGFLOW_API_KEY>"
```

### Q3: 评估过程中 LLM 调用超时

通义千问 API 偶尔会有延迟。脚本已设置 30 秒超时，如果频繁超时可以：
- 检查网络连接
- 减少测试集条数先做快速验证
- 在 `.env` 中将 `RAG_QUERY_REWRITE_MODEL` 设为 `qwen-turbo` 加速查询改写

### Q4: 如何只评估部分样本？

目前脚本会评估全部样本。如需部分评估，可临时编辑 `testset.json` 只保留目标条目，评估完后恢复。

### Q5: 想更换 judge 模型

编辑 `scripts/eval_ragas.py` 中 `run_ragas_evaluation()` 函数，修改 `ChatOpenAI` 的 `model` 参数。例如换用更快的 `qwen-turbo`：

```python
judge_llm = LangchainLLMWrapper(
    ChatOpenAI(
        model="qwen-turbo",  # 改这里
        ...
    )
)
```

---

## 八、后续优化建议

1. **定期评估**: 每次更新知识库或调整 RAG 参数后，重新运行评估对比分数变化
2. **扩充测试集**: 从真实用户提问中挑选典型问题补充到测试集
3. **自动化集成**: 可将评估脚本集成到 CI/CD 流程，设置分数阈值作为质量门禁
4. **多维度对比**: 保存历次 `results.json`，跟踪各指标随时间的变化趋势

---

## 九、首次评估结果（2026-03-29）

| 指标 | 得分 | 评价 |
|------|------|------|
| **Faithfulness** | 0.9833 | 优秀，回答高度忠实于检索内容 |
| **Answer Relevancy** | 0.9152 | 优秀，回答与问题高度相关 |
| **Context Precision** | 0.9058 | 优秀，检索排序质量高 |
| **Context Recall** | 1.0000 | 满分，检索完全覆盖标准答案 |

> 测试集: 20 条粮储领域 QA，覆盖 7 个知识类别。四项指标均在 0.9 以上，系统整体表现优秀。