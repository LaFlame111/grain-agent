# 粮情分析智能体 V010

基于大语言模型的粮仓监控与分析系统，支持自然语言对话查询粮温数据、生成分析报告和温度预测图表。

## 功能概览

- **自然语言对话**：用中文提问，自动调用工具查询/分析/预测
- **温度预测**：三层统计预测引擎（指数平滑 / Holt-Winters / STL 分解）
- **图表生成**：三温图、两湿图、折线图、热力图
- **报告生成**：一键生成 DOCX 格式完整分析报告
- **知识检索（RAG）**：检索粮储国家标准文件（需配置 RAGFlow）
- **本地数据导入**：支持将 Excel 原始数据转换后接入 Agent
- **双模型支持**：云端（通义千问）和本地部署模型均可使用

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/LaFlame111/grain-agent.git
cd grain-agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# Linux / Git Bash
cp .env.example .env

# Windows CMD
copy .env.example .env
```

打开 `.env`，至少填写：

```env
DASHSCOPE_API_KEY=你的阿里云DashScope_API_Key
```

> API Key 申请地址：https://dashscope.console.aliyun.com/

### 4. 启动服务

**Windows（Git Bash）：**
```bash
bash start.sh
```

**Windows（PowerShell）：**
```powershell
.\start_server.ps1
```

### 5. 打开前端

浏览器访问：**http://127.0.0.1:8000/ui**

> 注意：必须通过 `http://127.0.0.1:8000/ui` 访问，不要直接双击打开 HTML 文件（会有 CORS 问题）。

### 6. 停止服务

**Git Bash：**
```bash
bash stop.sh
```

**PowerShell：**
```powershell
.\stop_server.ps1
```

---

## 切换本地模型

如果你有本地部署的模型（Ollama / LM Studio / vLLM 等），修改 `.env`：

```env
# 注释掉云端配置
# LLM_MODEL=qwen-max
# LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 启用本地模型
LLM_MODEL=你的模型名称
LLM_BASE_URL=http://localhost:11434/v1   # 按实际地址修改
LLM_TIMEOUT=300                          # 本地模型推理慢，建议设大一些
```

修改后**必须重启服务器**才能生效。

---

## 导入 Excel 数据

将粮仓原始温度数据（Excel 格式）导入系统：

1. 将 Excel 文件放到项目根目录
2. 修改 `scripts/convert_excel_to_wms.py` 中的路径和仓房配置
3. 运行转换脚本：

```bash
python scripts/convert_excel_to_wms.py
```

4. 重启服务器，即可在前端查询导入的仓房

> 项目内置了驻马店直属库15号仓数据（2015-2018年，580条记录）作为示例。

---

## 目录结构

```
grain-agent/
├── app/
│   ├── api/           # FastAPI 路由
│   ├── core/          # 配置（config.py）
│   ├── models/        # 数据模型
│   └── services/      # 核心服务
│       ├── agent_service.py    # Agent 编排
│       ├── llm_service.py      # LLM 调用
│       ├── wms_client.py       # WMS 数据接口
│       ├── data_loader.py      # 本地数据加载
│       ├── rag_service.py      # RAG 知识检索
│       └── tools.py            # 12个工具（T1-T12）
├── data/
│   └── grain_data_wms_format.json   # 本地粮温数据
├── frontend/
│   └── test_ui/index.html           # 测试前端界面
├── scripts/
│   └── convert_excel_to_wms.py      # Excel 数据转换工具
├── data/knowledge/                  # RAG 知识库文档
├── start.sh                         # 启动脚本（Git Bash）
├── stop.sh                          # 停止脚本（Git Bash）
├── start_server.ps1                 # 启动脚本（PowerShell）
├── stop_server.ps1                  # 停止脚本（PowerShell）
├── .env.example                     # 环境变量模板
└── requirements.txt                 # Python 依赖
```

---

## API 接口

只暴露一个对话接口：

```
POST http://127.0.0.1:8000/api/v1/agent/chat
Content-Type: application/json

{"query": "查询15号仓最近的温度情况"}
```

响应：

```json
{
  "answer": "...",
  "reasoning": "...",
  "tool_calls": [...],
  "raw_results": {...}
}
```

---

## 健康检查

```
GET http://127.0.0.1:8000/
```

---

## 常见问题

**Q: 回答是"这是一个模拟回答"**  
A: API Key 无效或 LLM 调用超时。检查 `.env` 中的 `DASHSCOPE_API_KEY`，或增大 `LLM_TIMEOUT`。

**Q: 前端发消息没有响应**  
A: 确认通过 `http://127.0.0.1:8000/ui` 访问，不要用 `file://` 协议打开 HTML 文件。

**Q: 本地模型回答慢或超时**  
A: 在 `.env` 中设置 `LLM_TIMEOUT=300`，重启服务器。

**Q: 说"没有某某仓"**  
A: 该仓房可能只有本地数据没有对接WMS。确认已运行 `convert_excel_to_wms.py` 并重启服务器。
