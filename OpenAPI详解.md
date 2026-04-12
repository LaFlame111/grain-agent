# OpenAPI 详解

## 📋 什么是 OpenAPI？

**OpenAPI**（以前叫 Swagger）是一个**开放标准的 API 文档规范**，用于描述 RESTful API 的结构、请求参数、响应格式等信息。

### 核心概念

- **OpenAPI 规范**：描述 API 的 JSON/YAML 格式文档
- **OpenAPI 文档**：根据规范生成的交互式 API 文档
- **自动生成**：FastAPI 根据代码自动生成 OpenAPI 文档

### 为什么使用 OpenAPI？

1. ✅ **自动文档生成**：无需手动编写 API 文档，代码即文档
2. ✅ **交互式测试**：在文档页面直接测试 API
3. ✅ **代码生成**：可以根据 OpenAPI 规范生成客户端代码
4. ✅ **标准化**：遵循行业标准，便于团队协作
5. ✅ **类型安全**：自动验证请求和响应格式

---

## 🚀 FastAPI 中的 OpenAPI

### FastAPI 自动生成机制

FastAPI 会根据以下信息**自动生成** OpenAPI 文档：

1. **路由定义**：`@router.post("/chat")` 等装饰器
2. **Pydantic 模型**：`AgentChatRequest`, `AgentChatResponse` 等
3. **函数文档字符串**：端点的 docstring
4. **类型注解**：Python 类型提示

### 自动生成的内容

- ✅ **API 路径**：所有注册的路由
- ✅ **HTTP 方法**：GET, POST, PUT, DELETE 等
- ✅ **请求参数**：路径参数、查询参数、请求体
- ✅ **响应格式**：状态码、响应体结构
- ✅ **数据模型**：Pydantic 模型的 JSON Schema
- ✅ **示例值**：自动生成的示例数据

---

## ⚙️ V006 项目中的 OpenAPI 配置

### 1. FastAPI 应用初始化

```python
# V006/app/main.py

_docs_enabled = settings.DEBUG or settings.EXPOSE_DOCS
app = FastAPI(
    title=settings.PROJECT_NAME,  # "Grain Agent V006 - Agent Only"
    description="粮情分析智能体 - 纯 Agent 模式：仅提供自然语言对话接口，后台自动调用工具。",
    version="0.0.6",
    docs_url="/docs" if _docs_enabled else None,  # Swagger UI
    redoc_url="/redoc" if _docs_enabled else None,  # ReDoc UI
    openapi_url="/openapi.json" if _docs_enabled else None,  # OpenAPI JSON
)
```

**配置说明：**

| 参数 | 说明 | 默认值 | V006 配置 |
|------|------|--------|----------|
| `title` | API 标题 | "FastAPI" | "Grain Agent V006 - Agent Only" |
| `description` | API 描述 | `None` | 详细描述 |
| `version` | API 版本 | "0.0.6" | "0.0.6" |
| `docs_url` | Swagger UI 路径 | "/docs" | 条件启用 |
| `redoc_url` | ReDoc UI 路径 | "/redoc" | 条件启用 |
| `openapi_url` | OpenAPI JSON 路径 | "/openapi.json" | 条件启用 |

### 2. 文档启用条件

```python
_docs_enabled = settings.DEBUG or settings.EXPOSE_DOCS
```

**启用条件：**
- ✅ `DEBUG=true`：开发模式，自动启用文档
- ✅ `EXPOSE_DOCS=true`：生产环境显式启用文档
- ❌ 两者都为 `false`：文档被禁用（安全考虑）

**配置文件：** `V006/app/core/config.py`

```python
class Settings:
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    EXPOSE_DOCS: bool = os.getenv("EXPOSE_DOCS", "false").lower() == "true"
```

---

## 📍 访问 OpenAPI 文档

### 1. Swagger UI（推荐）

**访问地址：** `http://localhost:8000/docs`

**特点：**
- ✅ 交互式界面，可以直接测试 API
- ✅ 支持请求参数输入
- ✅ 显示请求/响应示例
- ✅ 可以查看数据模型

**界面功能：**
- **Try it out**：点击后可以输入参数并发送请求
- **Schemas**：查看所有数据模型的定义
- **Responses**：查看响应格式和示例

---

### 2. ReDoc UI（美观）

**访问地址：** `http://localhost:8000/redoc`

**特点：**
- ✅ 更美观的文档界面
- ✅ 适合阅读和分享
- ❌ 不支持交互式测试

---

### 3. OpenAPI JSON（原始数据）

**访问地址：** `http://localhost:8000/openapi.json`

**特点：**
- ✅ 原始 JSON 格式
- ✅ 可以被其他工具解析
- ✅ 用于代码生成和集成

**示例输出：**
```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Grain Agent V006 - Agent Only",
    "description": "粮情分析智能体 - 纯 Agent 模式...",
    "version": "0.0.6"
  },
  "paths": {
    "/api/v1/agent/chat": {
      "post": {
        "summary": "Agent Chat",
        "operationId": "agent_chat_agent_chat_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/AgentChatRequest"
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/AgentChatResponse"
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "AgentChatRequest": {
        "title": "AgentChatRequest",
        "type": "object",
        "properties": {
          "query": {
            "title": "Query",
            "type": "string"
          },
          "session_id": {
            "title": "Session Id",
            "type": "string"
          },
          "history": {
            "title": "History",
            "type": "array",
            "items": {
              "type": "object"
            }
          }
        },
        "required": ["query"]
      },
      "AgentChatResponse": {
        ...
      }
    }
  }
}
```

---

## 📊 OpenAPI JSON Schema 结构解析

### 1. 基本信息（`info`）

```json
{
  "openapi": "3.1.0",  // OpenAPI 规范版本
  "info": {
    "title": "Grain Agent V006 - Agent Only",
    "description": "粮情分析智能体 - 纯 Agent 模式...",
    "version": "0.0.6"
  }
}
```

**说明：**
- `openapi`：OpenAPI 规范版本（FastAPI 使用 3.1.0）
- `info.title`：API 标题（来自 `FastAPI(title=...)`）
- `info.description`：API 描述（来自 `FastAPI(description=...)`）
- `info.version`：API 版本（来自 `FastAPI(version=...)`）

---

### 2. 路径定义（`paths`）

```json
{
  "paths": {
    "/api/v1/agent/chat": {
      "post": {
        "summary": "Agent Chat",
        "operationId": "agent_chat_agent_chat_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/AgentChatRequest"
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/AgentChatResponse"
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**说明：**
- `paths`：所有 API 路径的集合
- `/api/v1/agent/chat`：完整的 API 路径
- `post`：HTTP 方法
- `summary`：端点摘要（来自函数 docstring）
- `operationId`：操作唯一标识符
- `requestBody`：请求体定义（引用 `AgentChatRequest`）
- `responses`：响应定义（引用 `AgentChatResponse`）

---

### 3. 数据模型（`components.schemas`）

```json
{
  "components": {
    "schemas": {
      "AgentChatRequest": {
        "title": "AgentChatRequest",
        "type": "object",
        "properties": {
          "query": {
            "title": "Query",
            "type": "string",
            "description": "用户的自然语言查询"
          },
          "session_id": {
            "title": "Session Id",
            "type": "string",
            "description": "会话ID（可选，用于多轮对话）"
          },
          "history": {
            "title": "History",
            "type": "array",
            "items": {
              "type": "object"
            },
            "default": []
          }
        },
        "required": ["query"]
      },
      "AgentChatResponse": {
        "title": "AgentChatResponse",
        "type": "object",
        "properties": {
          "trace_id": {
            "title": "Trace Id",
            "type": "string",
            "description": "追踪ID"
          },
          "query": {
            "title": "Query",
            "type": "string"
          },
          "intent": {
            "title": "Intent",
            "type": "string"
          },
          "answer": {
            "title": "Answer",
            "type": "string"
          },
          "reasoning": {
            "title": "Reasoning",
            "type": "string"
          },
          "tool_calls": {
            "title": "Tool Calls",
            "type": "array",
            "items": {
              "type": "object"
            }
          },
          "raw_results": {
            "title": "Raw Results",
            "type": "object"
          },
          "timestamp": {
            "title": "Timestamp",
            "type": "string",
            "format": "date-time"
          }
        },
        "required": ["trace_id", "query", "intent", "answer", "reasoning", "tool_calls", "raw_results", "timestamp"]
      }
    }
  }
}
```

**说明：**
- `components.schemas`：所有数据模型的定义
- 每个模型包含：
  - `title`：模型名称
  - `type`：数据类型（object, string, array 等）
  - `properties`：字段定义
  - `required`：必填字段列表

**字段属性：**
- `type`：字段类型（string, number, boolean, array, object）
- `description`：字段描述（来自 Pydantic `Field(description=...)`）
- `default`：默认值（来自 Pydantic 模型）
- `format`：格式（date-time, email, uuid 等）

---

## 🔧 如何自定义 OpenAPI 文档

### 1. 自定义端点信息

#### 使用函数文档字符串

```python
@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest):
    """
    Agent 智能对话接口
    
    用户可以用自然语言提问，Agent 会：
    1. 识别用户意图
    2. 自动选择合适的工具（T1-T8）
    3. 执行工具链
    4. 生成回答
    
    支持的查询类型：
    - 单仓查询: "1号仓的粮温情况如何？"
    - 仓间对比: "1号仓和2号仓哪个温度更高？"
    - 时间对比: "1号仓这周温度比上周高吗？"
    - 全库巡检: "巡检一下所有粮仓"
    
    示例请求:
    {
        "query": "1号仓的粮温情况如何？请给出储藏建议。"
    }
    """
    # ...
```

**效果：**
- 文档字符串的第一行会成为 `summary`
- 完整文档字符串会成为 `description`
- 显示在 Swagger UI 的端点说明中

---

#### 使用 `summary` 和 `description` 参数

```python
@router.post(
    "/chat",
    response_model=AgentChatResponse,
    summary="Agent 智能对话",
    description="用户可以用自然语言提问，Agent 会自动识别意图并调用工具。",
    tags=["Agent"]
)
def agent_chat(request: AgentChatRequest):
    # ...
```

---

### 2. 自定义响应状态码

```python
from fastapi import status

@router.post(
    "/chat",
    response_model=AgentChatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "成功响应",
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/AgentChatResponse"}
                }
            }
        },
        422: {
            "description": "请求验证失败",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "query"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "服务器内部错误"
        }
    }
)
def agent_chat(request: AgentChatRequest):
    # ...
```

---

### 3. 自定义字段描述

#### 使用 Pydantic `Field`

```python
from pydantic import BaseModel, Field

class AgentChatRequest(BaseModel):
    """Agent 对话请求"""
    query: str = Field(
        ...,
        description="用户的自然语言查询",
        example="1号仓的粮温情况如何？"
    )
    session_id: Optional[str] = Field(
        None,
        description="会话ID（可选，用于多轮对话）",
        example="session-12345"
    )
    history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="历史对话记录（可选）",
        example=[{"role": "user", "content": "之前的查询"}]
    )
```

**效果：**
- `description`：显示在 Swagger UI 的字段说明中
- `example`：显示示例值
- `...`：表示必填字段

---

### 4. 自定义 OpenAPI Schema

#### 修改 OpenAPI JSON 结构

```python
from fastapi.openapi.utils import get_openapi

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Grain Agent V006",
        version="0.0.6",
        description="粮情分析智能体 API",
        routes=app.routes,
    )
    
    # 自定义修改
    openapi_schema["info"]["x-logo"] = {
        "url": "https://example.com/logo.png"
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

---

### 5. 添加标签和分组

```python
# V006/app/api/v1/api.py
api_router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"]  # 添加标签
)
```

**效果：**
- 在 Swagger UI 中，所有 `tags=["Agent"]` 的端点会被分组显示
- 便于查找和管理相关端点

---

## 📝 V006 项目中的实际示例

### 1. Agent 端点定义

```python
# V006/app/api/v1/endpoints/agent.py

@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest):
    """
    Agent 智能对话接口
    
    用户可以用自然语言提问，Agent 会：
    1. 识别用户意图
    2. 自动选择合适的工具（T1-T8）
    3. 执行工具链
    4. 生成回答
    """
    # ...
```

**生成的 OpenAPI 文档包含：**
- ✅ 路径：`POST /api/v1/agent/chat`
- ✅ 请求体：`AgentChatRequest` 模型
- ✅ 响应：`AgentChatResponse` 模型
- ✅ 描述：函数文档字符串

---

### 2. 请求模型定义

```python
# V006/app/models/schemas.py

class AgentChatRequest(BaseModel):
    """Agent 对话请求"""
    query: str  # 用户的自然语言查询
    session_id: Optional[str] = None  # 会话ID（可选）
    history: List[Dict[str, str]] = [] # 历史对话
```

**生成的 OpenAPI Schema：**
```json
{
  "AgentChatRequest": {
    "title": "AgentChatRequest",
    "type": "object",
    "properties": {
      "query": {
        "title": "Query",
        "type": "string"
      },
      "session_id": {
        "title": "Session Id",
        "type": "string"
      },
      "history": {
        "title": "History",
        "type": "array",
        "items": {
          "type": "object"
        },
        "default": []
      }
    },
    "required": ["query"]
  }
}
```

---

### 3. 响应模型定义

```python
# V006/app/models/schemas.py

class AgentChatResponse(BaseResponse):
    """Agent 对话响应"""
    query: str  # 用户查询
    intent: str  # 识别的意图
    answer: str  # Agent 的回答
    reasoning: str  # 推理过程
    tool_calls: List[Dict[str, Any]]  # 调用的工具列表
    raw_results: Dict[str, Any]  # 原始结果
    timestamp: datetime
```

**生成的 OpenAPI Schema：**
```json
{
  "AgentChatResponse": {
    "title": "AgentChatResponse",
    "type": "object",
    "properties": {
      "trace_id": {
        "title": "Trace Id",
        "type": "string",
        "description": "追踪ID"
      },
      "query": {
        "title": "Query",
        "type": "string"
      },
      "intent": {
        "title": "Intent",
        "type": "string"
      },
      "answer": {
        "title": "Answer",
        "type": "string"
      },
      "reasoning": {
        "title": "Reasoning",
        "type": "string"
      },
      "tool_calls": {
        "title": "Tool Calls",
        "type": "array",
        "items": {
          "type": "object"
        }
      },
      "raw_results": {
        "title": "Raw Results",
        "type": "object"
      },
      "timestamp": {
        "title": "Timestamp",
        "type": "string",
        "format": "date-time"
      }
    },
    "required": ["trace_id", "query", "intent", "answer", "reasoning", "tool_calls", "raw_results", "timestamp"]
  }
}
```

---

## 🧪 使用 OpenAPI 文档测试 API

### 1. 在 Swagger UI 中测试

1. **访问文档：** `http://localhost:8000/docs`
2. **找到端点：** 展开 `POST /api/v1/agent/chat`
3. **点击 "Try it out"**
4. **输入请求参数：**
   ```json
   {
     "query": "1号仓的粮温情况如何？请给出储藏建议。"
   }
   ```
5. **点击 "Execute"**
6. **查看响应：**
   - 响应状态码
   - 响应体内容
   - 响应头信息

---

### 2. 使用 curl 测试（基于 OpenAPI 文档）

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "1号仓的粮温情况如何？请给出储藏建议。"
  }'
```

---

### 3. 使用 Python requests（基于 OpenAPI 文档）

```python
import requests

url = "http://localhost:8000/api/v1/agent/chat"
payload = {
    "query": "1号仓的粮温情况如何？请给出储藏建议。"
}

response = requests.post(url, json=payload)
result = response.json()

print(f"回答: {result['answer']}")
print(f"推理: {result['reasoning']}")
print(f"调用的工具: {result['tool_calls']}")
```

---

## 🔍 OpenAPI 文档的生成流程

### FastAPI 自动生成流程

```
FastAPI 应用启动
    ↓
扫描所有路由装饰器 (@router.post, @router.get 等)
    ↓
提取端点信息：
  - 路径、HTTP 方法
  - 请求参数（路径参数、查询参数、请求体）
  - 响应模型
  - 函数文档字符串
    ↓
扫描所有 Pydantic 模型
    ↓
生成 JSON Schema：
  - 字段类型、描述、默认值
  - 必填字段列表
  - 嵌套模型引用
    ↓
构建 OpenAPI JSON 结构
    ↓
提供三个访问入口：
  - /docs (Swagger UI)
  - /redoc (ReDoc UI)
  - /openapi.json (原始 JSON)
```

---

## 🎯 OpenAPI 文档的优势

### 1. 代码即文档

**传统方式：**
- ❌ 需要手动编写和维护 API 文档
- ❌ 代码和文档容易不一致
- ❌ 更新文档容易遗漏

**FastAPI + OpenAPI：**
- ✅ 代码即文档，自动生成
- ✅ 代码和文档始终保持一致
- ✅ 修改代码自动更新文档

---

### 2. 交互式测试

**传统方式：**
- ❌ 需要使用 Postman、curl 等工具测试
- ❌ 需要手动构造请求参数
- ❌ 需要查看代码才能知道参数格式

**FastAPI + OpenAPI：**
- ✅ 在文档页面直接测试
- ✅ 自动显示参数格式和示例
- ✅ 实时查看响应结果

---

### 3. 类型安全

**传统方式：**
- ❌ 请求参数类型不明确
- ❌ 容易传错参数类型
- ❌ 运行时才发现错误

**FastAPI + OpenAPI：**
- ✅ Pydantic 自动验证类型
- ✅ 文档中明确显示类型要求
- ✅ 请求前就能发现类型错误

---

### 4. 团队协作

**传统方式：**
- ❌ 前端需要查看后端代码才能知道 API 格式
- ❌ 需要手动编写 API 调用代码
- ❌ 容易产生误解

**FastAPI + OpenAPI：**
- ✅ 前端可以直接查看文档了解 API
- ✅ 可以根据 OpenAPI JSON 生成客户端代码
- ✅ 减少沟通成本

---

## 📚 相关文档

- **`V006/agent端点详解.md`**：Agent 端点的详细说明
- **`V006/路由机制详解.md`**：FastAPI 路由系统详解
- **`V006/模型层详解.md`**：Pydantic 模型的使用
- **`V006/Pydantic模型对象详解.md`**：Pydantic 模型对象详解

---

## 🎯 总结

OpenAPI 是 FastAPI 的**核心特性**之一，提供了：

1. ✅ **自动文档生成**：根据代码自动生成 API 文档
2. ✅ **交互式测试**：在文档页面直接测试 API
3. ✅ **类型安全**：自动验证请求和响应格式
4. ✅ **标准化**：遵循 OpenAPI 3.1.0 规范
5. ✅ **易于集成**：可以被其他工具解析和使用

**V006 项目中的配置：**
- 📍 Swagger UI：`http://localhost:8000/docs`
- 📍 ReDoc UI：`http://localhost:8000/redoc`
- 📍 OpenAPI JSON：`http://localhost:8000/openapi.json`
- ⚙️ 启用条件：`DEBUG=true` 或 `EXPOSE_DOCS=true`

**关键代码：**
```python
app = FastAPI(
    title="Grain Agent V006 - Agent Only",
    description="粮情分析智能体 - 纯 Agent 模式...",
    version="0.0.6",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)
```

