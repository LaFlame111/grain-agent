# Pydantic 模型对象详解

## 📋 什么是 Pydantic 模型对象？

**Pydantic 模型对象**是基于 Pydantic 库创建的 Python 类实例，它提供了**数据验证**、**类型转换**和**序列化**功能。

在 V006 项目中，所有的 `domain.py` 和 `schemas.py` 中的类都继承自 `BaseModel`，因此它们都是 **Pydantic 模型对象**。

---

## 🎯 核心特性

### 1. **自动数据验证**

Pydantic 会自动验证输入数据的类型和格式，不符合要求的数据会抛出 `ValidationError`。

**示例：**

```python
from app.models.domain import WarehouseInfo

# ✅ 正确：所有必需字段都提供了
warehouse = WarehouseInfo(
    house_code="1",
    house_name="1号仓",
    depot_name="中央储备粮某直属库",
    house_type_name="平房仓",
    construction_year="2010",
    design_capacity=5000.0,
    authorized_capacity=4800.0
)
print(warehouse.house_name)  # 输出: "1号仓"

# ❌ 错误：缺少必需字段
try:
    warehouse = WarehouseInfo(
        house_code="1",
        # house_name 缺失 → 会抛出 ValidationError
    )
except Exception as e:
    print(f"验证失败: {e}")
```

---

### 2. **自动类型转换**

Pydantic 会尝试将输入数据转换为定义的类型。

**示例：**

```python
from app.models.domain import Reading
from datetime import datetime

# ✅ 字符串会自动转换为 datetime
reading = Reading(
    sensor_id="S1",
    timestamp="2024-01-01 12:00:00",  # 字符串
    value="25.5",  # 字符串会自动转换为 float
    type="temperature"
)

print(type(reading.timestamp))  # <class 'datetime.datetime'>
print(type(reading.value))       # <class 'float'>
```

---

### 3. **默认值和可选字段**

可以使用 `Optional` 和默认值来定义可选字段。

**示例：**

```python
from app.models.domain import WarehouseInfo

# ✅ 可选字段可以不提供
warehouse = WarehouseInfo(
    house_code="1",
    house_name="1号仓",
    depot_name="中央储备粮某直属库",
    house_type_name="平房仓",
    construction_year="2010",
    design_capacity=5000.0,
    authorized_capacity=4800.0,
    # structure_wall 是可选的，可以不提供
    # outer_length 是可选的，可以不提供
)

print(warehouse.structure_wall)  # None（因为未提供）
print(warehouse.outer_length)    # None（因为未提供）
```

---

### 4. **序列化和反序列化**

Pydantic 模型对象可以轻松转换为字典或 JSON 字符串。

**示例：**

```python
from app.models.domain import WarehouseInfo
import json

# 创建模型对象
warehouse = WarehouseInfo(
    house_code="1",
    house_name="1号仓",
    depot_name="中央储备粮某直属库",
    house_type_name="平房仓",
    construction_year="2010",
    design_capacity=5000.0,
    authorized_capacity=4800.0
)

# 转换为字典
warehouse_dict = warehouse.dict()
print(warehouse_dict)
# {
#     'house_code': '1',
#     'house_name': '1号仓',
#     'depot_name': '中央储备粮某直属库',
#     ...
# }

# 转换为 JSON 字符串
warehouse_json = warehouse.json()
print(warehouse_json)
# {"house_code":"1","house_name":"1号仓",...}

# 从字典创建对象
warehouse2 = WarehouseInfo(**warehouse_dict)
```

---

### 5. **字段验证和约束**

使用 `Field()` 可以添加字段描述、验证规则等。

**示例：**

```python
from pydantic import BaseModel, Field

class WarehouseInfo(BaseModel):
    house_code: str = Field(..., description="仓房编码")
    # ... 表示必需字段
    # description 用于文档说明
    
    design_capacity: float = Field(..., description="设计仓容", gt=0)
    # gt=0 表示必须大于 0
```

---

## 🔍 在 V006 项目中的使用

### 1. **API 请求验证** (`schemas.py`)

FastAPI 自动使用 Pydantic 模型验证 HTTP 请求。

```python
# V006/app/api/v1/endpoints/agent.py

@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(request: AgentChatRequest):
    # FastAPI 自动验证 request 是否符合 AgentChatRequest 的定义
    # 如果不符合，会返回 422 错误
    print(request.query)  # 可以直接使用，类型已保证是 str
```

**流程：**
```
HTTP JSON 请求
    ↓
FastAPI 自动验证
    ↓
AgentChatRequest 对象（Pydantic 模型对象）
    ↓
可以直接使用 request.query, request.session_id 等
```

---

### 2. **API 响应序列化** (`schemas.py`)

FastAPI 自动将 Pydantic 模型对象序列化为 JSON。

```python
# V006/app/api/v1/endpoints/agent.py

return AgentChatResponse(**response)
# FastAPI 自动将 AgentChatResponse 对象转换为 JSON
```

**流程：**
```
AgentChatResponse 对象（Pydantic 模型对象）
    ↓
FastAPI 自动序列化
    ↓
HTTP JSON 响应
```

---

### 3. **业务数据构造** (`domain.py`)

WMSClient 从 WMS API 获取数据后，构造 Pydantic 模型对象。

```python
# V006/app/services/wms_client.py

def get_warehouse_info(self, house_code: str) -> WarehouseInfo:
    # 从 WMS API 获取 JSON 数据
    # 构造 WarehouseInfo 对象
    return WarehouseInfo(
        house_code=house_code,
        house_name=f"{house_code}号仓",
        depot_name="中央储备粮某直属库",
        # ...
    )
```

**流程：**
```
WMS API JSON 数据
    ↓
构造 WarehouseInfo 对象（Pydantic 模型对象）
    ↓
返回给调用者，类型安全
```

---

### 4. **数据传递** (`domain.py` → `schemas.py`)

Domain 模型对象可以在 Schemas 中组合使用。

```python
# V006/app/models/schemas.py

class WarehouseInfoResponse(BaseResponse):
    data: WarehouseInfo  # 使用 Domain 模型

# 使用时：
response = WarehouseInfoResponse(
    trace_id="123",
    data=warehouse_info  # WarehouseInfo 对象
)
```

---

## 📊 Pydantic 模型对象 vs 普通 Python 对象

| 特性 | Pydantic 模型对象 | 普通 Python 对象 |
|------|------------------|------------------|
| **类型验证** | ✅ 自动验证 | ❌ 需要手动检查 |
| **类型转换** | ✅ 自动转换 | ❌ 需要手动转换 |
| **默认值** | ✅ 支持 | ✅ 支持 |
| **序列化** | ✅ `.dict()`, `.json()` | ❌ 需要手动实现 |
| **文档生成** | ✅ 自动生成 OpenAPI 文档 | ❌ 需要手动编写 |
| **IDE 支持** | ✅ 类型提示完整 | ⚠️ 取决于实现 |

---

## 💡 实际代码示例

### 示例 1：创建和使用模型对象

```python
from app.models.domain import WarehouseInfo

# 创建对象
warehouse = WarehouseInfo(
    house_code="1",
    house_name="1号仓",
    depot_name="中央储备粮某直属库",
    house_type_name="平房仓",
    construction_year="2010",
    design_capacity=5000.0,
    authorized_capacity=4800.0
)

# 访问属性（类型安全）
print(warehouse.house_name)        # str
print(warehouse.design_capacity)   # float

# 转换为字典
data = warehouse.dict()
print(data["house_name"])

# 转换为 JSON
json_str = warehouse.json()
print(json_str)
```

---

### 示例 2：FastAPI 自动验证

```python
from fastapi import FastAPI
from app.models.schemas import AgentChatRequest

app = FastAPI()

@app.post("/chat")
def chat(request: AgentChatRequest):
    # request 已经是 AgentChatRequest 对象
    # FastAPI 已经验证了所有字段
    # 如果验证失败，FastAPI 会自动返回 422 错误
    
    return {"answer": f"您的问题是: {request.query}"}
```

**请求示例：**
```json
{
    "query": "1号仓的粮温情况如何？",
    "session_id": "session-123",
    "history": []
}
```

**如果请求缺少 `query` 字段：**
```json
{
    "session_id": "session-123"
}
```

FastAPI 会自动返回：
```json
{
    "detail": [
        {
            "loc": ["body", "query"],
            "msg": "field required",
            "type": "value_error.missing"
        }
    ]
}
```

---

### 示例 3：嵌套模型对象

```python
from app.models.domain import Silo, Sensor

# 创建嵌套对象
silo = Silo(
    id="1",
    name="1号仓",
    capacity=5000.0,
    current_level=4500.0,
    sensors=[
        Sensor(id="S1", type="temperature", location={"x": 1.0, "y": 2.0, "z": 3.0}),
        Sensor(id="S2", type="humidity", location={"x": 2.0, "y": 3.0, "z": 4.0})
    ]
)

# 访问嵌套对象
print(silo.sensors[0].id)  # "S1"
print(silo.sensors[0].location["x"])  # 1.0
```

---

### 示例 4：从字典创建对象

```python
from app.models.domain import WarehouseInfo

# 从字典创建
data = {
    "house_code": "1",
    "house_name": "1号仓",
    "depot_name": "中央储备粮某直属库",
    "house_type_name": "平房仓",
    "construction_year": "2010",
    "design_capacity": 5000.0,
    "authorized_capacity": 4800.0
}

warehouse = WarehouseInfo(**data)
print(warehouse.house_name)  # "1号仓"
```

---

## 🎓 关键概念总结

### 1. **BaseModel**

所有 Pydantic 模型都继承自 `BaseModel`：

```python
from pydantic import BaseModel

class MyModel(BaseModel):
    name: str
    age: int
```

---

### 2. **Field()**

用于定义字段的详细配置：

```python
from pydantic import BaseModel, Field

class MyModel(BaseModel):
    name: str = Field(..., description="名称", min_length=1)
    # ... 表示必需字段
    # description 用于文档说明
    # min_length 表示最小长度
```

---

### 3. **类型提示**

Pydantic 使用 Python 类型提示来定义字段类型：

```python
from typing import List, Optional, Dict

class MyModel(BaseModel):
    name: str                    # 必需字段
    age: Optional[int] = None   # 可选字段
    tags: List[str] = []        # 列表字段
    metadata: Dict[str, Any]    # 字典字段
```

---

### 4. **验证错误**

如果数据不符合要求，Pydantic 会抛出 `ValidationError`：

```python
from pydantic import ValidationError
from app.models.domain import WarehouseInfo

try:
    warehouse = WarehouseInfo(
        house_code="1",
        # 缺少必需字段
    )
except ValidationError as e:
    print(e.json())
    # 输出详细的验证错误信息
```

---

## 🔗 在 V006 项目中的完整流程

```
1. HTTP 请求 (JSON)
   ↓
2. FastAPI 接收请求
   ↓
3. 使用 Schemas (AgentChatRequest) 验证
   → 如果验证失败，返回 422 错误
   → 如果验证成功，创建 AgentChatRequest 对象
   ↓
4. AgentService 处理
   ↓
5. WMSClient 获取数据
   ↓
6. 构造 Domain 模型对象 (WarehouseInfo, GrainTempData)
   ↓
7. Tools 处理 Domain 对象
   ↓
8. AnalysisService 返回 Schemas 对象 (AnalysisResult)
   ↓
9. AgentService 构建响应字典
   ↓
10. 构造 Schemas 对象 (AgentChatResponse)
    ↓
11. FastAPI 自动序列化为 JSON
    ↓
12. HTTP 响应 (JSON)
```

---

## 📚 参考资源

- [Pydantic 官方文档](https://docs.pydantic.dev/)
- [FastAPI 数据验证](https://fastapi.tiangolo.com/tutorial/body/)
- V006 项目中的实际使用：
  - `V006/app/models/domain.py` - Domain 模型定义
  - `V006/app/models/schemas.py` - Schemas 模型定义
  - `V006/app/api/v1/endpoints/agent.py` - API 端点使用示例

---

## 🎯 总结

**Pydantic 模型对象**是 V006 项目中数据验证和类型安全的核心：

1. ✅ **自动验证**：确保数据符合预期格式
2. ✅ **类型安全**：IDE 可以提供完整的类型提示
3. ✅ **易于序列化**：轻松转换为字典或 JSON
4. ✅ **文档生成**：FastAPI 自动生成 API 文档
5. ✅ **代码简洁**：减少手动验证和转换代码

在 V006 项目中，所有的 `domain.py` 和 `schemas.py` 中的类都是 Pydantic 模型对象，它们确保了整个系统的数据一致性和类型安全。

