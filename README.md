# 粮情分析智能体 V008 - 进化版本 (Evolutionary)

## 🎯 版本概述

V008 版本是**进化版本**，在 V007 基础上实现了**真实 HTTP API 集成**、**粮情趋势预测**以及**独立图表工具**。

**核心改进**：
- ✅ **真实 API 对接**：正式对接 WMS 系统真实 HTTP REST API，不再依赖本地 JSON。
- ✅ **粮情趋势预测**：新增 T9 工具，支持基于历史数据进行短期粮情预测。
- ✅ **独立图表工具**：将三温图和两湿图作为独立工具暴露给 Agent，支持按需生成。
- ✅ **接口规范对齐**：全面对齐 WMS 系统新修改的 4 个核心接口规范。
- ✅ **Word 报告增强**：报告中自动集成趋势预测章节。

## 🔌 WMS 真实接口对接

本版本已全面对接以下真实 API（Base URL: `http://121.40.162.1:8017`）：

1. **仓房列表**: `/api/wms/warehouse/list`
2. **仓房信息**: `/api/wms/warehouse/info` (支持 `house_code`)
3. **粮温数据**: `/api/wms/grain/temperature` (支持 `house_code`, `start_time`, `end_time`)
4. **气体浓度**: `/api/wms/gas/concentration` (支持 `house_code`, `start_time`, `end_time`)

## 🏗️ 架构设计

V008 延续 **Agent-Only** 架构，但在 `Outbound` 层进行了升级：

* **Inbound**: 仅暴露单一入口 `/api/v1/agent/chat`。
* **Core**:
  * **Intent Recognition**: LLM 分析用户意图。
  * **Tool Execution**: 自动调度 `GrainTools` (T1-T11)。
* **Outbound**: 通过 `WMSClient` 发起异步 HTTP 请求获取实时数据。

## 🚀 快速开始

### 1. 环境准备

```bash
cd V008
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，并配置您的 API Key。

### 3. 启动服务

```bash
# Windows PowerShell
.\start_server.ps1
```

### 4. 验证测试

```bash
# 测试真实 API 集成
python test_v008_real_api.py

# 测试 Agent 整体流程
python test_agent_v008.py
```

## 📂 文件结构

* `app/core/wms_endpoints.py`: WMS 接口地址统一配置。
* `app/services/wms_client.py`: 封装 HTTP 请求与数据适配逻辑。
* `app/services/tools.py`: 核心业务逻辑 (T1-T11)，包含新增的预测和图表工具。
* `test_v008_real_api.py`: 针对真实接口的集成测试脚本。

---

*最后更新：2026-01-04*
