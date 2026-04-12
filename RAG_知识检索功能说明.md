# RAG 知识检索功能说明

## 一、功能概述

为粮情分析智能体新增 `knowledge_search` 工具，让 LLM 在回答储粮标准、操作规程、安全阈值等专业问题时，能主动从向量知识库中检索国标/SOP 原文片段作为回答依据，而非仅依赖模型自身知识。

### 技术方案

| 组件 | 选型 | 说明 |
|------|------|------|
| 向量数据库 | ChromaDB（嵌入式） | 本地持久化存储，无需外部服务 |
| Embedding 模型 | DashScope `text-embedding-v3` | 复用现有 API Key，通过 OpenAI SDK 调用 |
| 集成方式 | LLM Function Calling | 与现有工具一致，LLM 按需调用 |
| 知识来源 | `data/knowledge/` 目录 | 支持 `.md` / `.txt` / `.docx` / `.pdf` |

---

## 二、新增依赖

| 库名 | 版本要求 | 用途 |
|------|---------|------|
| `chromadb` | >=0.5.0 | 向量数据库，存储和检索知识文档 |
| `pdfplumber` | >=0.10.0 | 读取 PDF 文件内容 |
| `python-docx` | >=1.1.0 | 读取 Word 文档内容（项目已有） |
| `openai` | >=1.0.0 | 调用 DashScope Embedding API（项目已有） |

安装命令：

```bash
pip install chromadb pdfplumber
```

---

## 三、新增/修改文件清单

### 新增文件

| 文件路径 | 说明 |
|---------|------|
| `app/services/rag_service.py` | RAG 核心服务（约 160 行） |
| `scripts/__init__.py` | 空包文件 |
| `scripts/build_knowledge_index.py` | 知识库索引构建脚本（约 230 行） |
| `data/knowledge/grain_storage_standards.md` | 示例知识文档 |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `requirements.txt` | 添加 `chromadb`、`pdfplumber` 依赖 |
| `app/core/config.py` | 添加 `EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS` 配置项 |
| `app/services/tool_definitions.py` | 注册 `knowledge_search` 工具 JSON Schema |
| `app/services/agent_service.py` | 导入 RAG 服务、注册工具映射、新增桥接方法、更新 System Prompt |
| `.env` | 添加 `EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS` 环境变量 |

---

## 四、核心模块说明

### 4.1 RAG 服务 — `app/services/rag_service.py`

#### 类：`RAGService`

| 方法/属性 | 说明 |
|----------|------|
| `_initialize()` | 初始化 ChromaDB 客户端和 Embedding 客户端，任何失败均静默降级，不影响其他功能 |
| `is_available` (属性) | 返回 `bool`，知识库未构建或初始化失败时为 `False` |
| `search(query, top_k=3)` | 核心检索方法，返回与现有工具格式一致的 dict |

#### 单例函数：`get_rag_service()`

参照 `data_loader.py` 的 `get_data_loader()` 模式，全局维护唯一实例。

#### `search()` 返回格式

成功时：
```json
{
    "status": "success",
    "query": "小麦安全温度",
    "total_results": 3,
    "results": [
        {
            "content": "安全温度：粮温 ≤ 25°C，储粮状态良好...",
            "source": "grain_storage_standards.md",
            "title": "粮食储藏温度标准",
            "relevance_score": 0.8721
        }
    ]
}
```

不可用时：
```json
{
    "status": "unavailable",
    "message": "知识库未构建或初始化失败，请先运行 build_knowledge_index 脚本。",
    "results": []
}
```

### 4.2 索引构建脚本 — `scripts/build_knowledge_index.py`

#### 文件读取函数

| 函数 | 说明 |
|------|------|
| `read_file(fpath)` | 根据扩展名自动分派到对应读取器 |
| `read_docx(fpath)` | 使用 `python-docx` 提取段落文本 |
| `read_pdf(fpath)` | 使用 `pdfplumber` 逐页提取文本 |

#### 分块函数

| 函数 | 说明 |
|------|------|
| `split_by_markdown_heading(text)` | 按 `#` 标题拆分为 `[{title, content}]` 列表 |
| `split_long_section(text, max_chars=500, overlap=50)` | 超长段落按段落边界二次切分，相邻块保留 50 字符重叠 |
| `load_and_chunk(knowledge_dir)` | 读取目录下所有文件并分块，返回 `[{id, text, metadata}]` |

#### Embedding 函数

| 函数 | 说明 |
|------|------|
| `embed_texts(texts, client, model, dimensions)` | 批量调用 DashScope Embedding API，每批 20 条 |

#### 分块策略

```
原始文档
  │
  ▼
按 Markdown 标题（#/##/###/####）拆分为段落
  │
  ▼
每段 ≤ 500 字？──是──▶ 直接作为一个块
  │
  否
  ▼
按空行（段落边界）二次切分，相邻块重叠 50 字符
```

#### 配置常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `CHUNK_MAX_CHARS` | 500 | 单块最大字符数 |
| `CHUNK_OVERLAP` | 50 | 相邻块重叠字符数 |
| `EMBEDDING_BATCH_SIZE` | 20 | 每批 Embedding 条数 |
| `COLLECTION_NAME` | `grain_knowledge` | ChromaDB Collection 名称 |

### 4.3 工具定义 — `tool_definitions.py` 中新增

```python
{
    "name": "knowledge_search",
    "description": "粮储知识检索：从国家标准（GB/T 29890等）、操作规程（通风/熏蒸SOP）、安全阈值等专业知识库中检索相关信息。",
    "parameters": {
        "query": "检索查询文本（必填）",
        "top_k": "返回片段数量，默认3（选填）"
    }
}
```

### 4.4 Agent 集成 — `agent_service.py` 改动

- 工具映射：`"knowledge_search": self._knowledge_search`
- 桥接方法：`_knowledge_search(query, top_k=3)` → 调用 `get_rag_service().search()`
- System Prompt 新增规则 5：当用户询问储粮标准、操作规程、安全阈值、最佳实践时，调用 `knowledge_search` 工具

### 4.5 环境变量 — `.env`

| 变量名 | 默认值 | 说明 |
|--------|-------|------|
| `EMBEDDING_MODEL` | `text-embedding-v3` | DashScope Embedding 模型名 |
| `EMBEDDING_DIMENSIONS` | `1024` | Embedding 向量维度 |

---

## 五、运行指南

### 5.1 安装依赖

```bash
pip install -r requirements.txt
```

### 5.2 准备知识文档

将知识文件放到 `V008/data/knowledge/` 目录下：

```
V008/data/knowledge/
├── grain_storage_standards.md    ← 已提供的示例文档
├── your_document.docx            ← 支持 Word 文档
├── your_standard.pdf             ← 支持 PDF 文件
└── your_notes.txt                ← 支持纯文本
```

建议：`.md` 文件使用 Markdown 标题组织内容，分块效果最佳。

### 5.3 构建知识库索引

```bash
cd V008
python -m scripts.build_knowledge_index
```

成功输出示例：
```
2026-03-21 22:10:00 [INFO] 处理文件: grain_storage_standards.md
2026-03-21 22:10:00 [INFO] 共生成 12 个文本块
2026-03-21 22:10:01 [INFO] 开始生成 Embedding（模型: text-embedding-v3，维度: 1024）...
2026-03-21 22:10:02 [INFO]   Embedding 批次 1 完成 (12 条)
2026-03-21 22:10:02 [INFO] 索引构建完成！共写入 12 个文本块到 V008/data/chroma_db
```

> 每次运行会**自动清除旧索引并全量重建**。仅在新增或修改知识文档后需要重新运行。

### 5.4 启动服务

```bash
cd V008
uvicorn app.main:app
```

启动日志中会出现：
```
RAG 知识检索服务初始化成功，collection 文档数: 12
```

### 5.5 测试验证

发送以下查询测试 `knowledge_search` 工具是否被正确调用：

| 测试查询 | 预期行为 |
|---------|---------|
| "小麦储存的安全温度标准是多少？" | 触发 `knowledge_search`，返回温度阈值 |
| "什么条件下应该启动机械通风？" | 触发 `knowledge_search`，返回通风 SOP |
| "磷化氢熏蒸的安全浓度是多少？" | 触发 `knowledge_search`，返回气体标准 |
| "1号仓当前温度是多少？" | **不触发**，走正常数据查询 |

快速验证：

```bash
cd V008
python test_rag.py
该脚本测试 RAG 功能是否正常，包括可用性、搜索结果等。
```
```bash
cd v008
python test_rag_e2e.py
该脚本通过API做端到端测试，看LLM是否会调用knowledge_search工具，并引用知识库内容来回答。
```

---

## 六、静默降级机制

RAG 功能在以下情况下会自动降级为"不可用"，**不影响其他工具正常运行**：

| 场景 | 表现 |
|------|------|
| 未安装 `chromadb` | 日志提示依赖缺失，`is_available = False` |
| `data/chroma_db/` 目录不存在 | 日志提示未构建索引，`is_available = False` |
| Collection 为空 | 日志提示为空，`is_available = False` |
| Embedding API 调用失败 | `search()` 返回 `{"status": "error", ...}` |

LLM 调用 `knowledge_search` 时收到不可用响应后，会基于自身知识继续回答。

---

## 七、目录结构总览

```
V008/
├── app/
│   ├── core/
│   │   └── config.py               ← 新增 EMBEDDING_MODEL / EMBEDDING_DIMENSIONS
│   └── services/
│       ├── agent_service.py         ← 注册 knowledge_search 工具
│       ├── rag_service.py           ← 【新增】RAG 核心服务
│       └── tool_definitions.py      ← 新增 knowledge_search JSON Schema
├── scripts/
│   ├── __init__.py                  ← 【新增】空包文件
│   └── build_knowledge_index.py     ← 【新增】索引构建脚本
├── data/
│   ├── knowledge/                   ← 【新增】知识文档目录
│   │   └── grain_storage_standards.md
│   └── chroma_db/                   ← 【构建后生成】向量数据库存储
├── requirements.txt                 ← 新增 chromadb / pdfplumber
└── .env                             ← 新增 Embedding 配置
```
