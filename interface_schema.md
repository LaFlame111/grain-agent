# WMS 标准接口 Schema 定义

根据《真实接口类别.pdf》提取的内容，以下是智能体需要调用的 WMS（粮库业务管理系统）标准数据接口 Schema 定义。

**注意**：这些接口作为内部工具暴露给 LLM，通过 Function Calling 机制被 Agent 自动调用。实际实现位于 `app/services/wms_client.py`，通过 `app/services/tools.py` 封装后提供给 Agent。

## 1. 接口列表

| 接口名称 | 功能描述 | 输入参数 | 输出数据 |
| :--- | :--- | :--- | :--- |
| `get_connected_silos` | 获取接入智能体的粮仓清单 | 无 | 包含 house_code, house_name, short_name 的列表 |
| `get_warehouse_info` | 查询仓房基本信息 | 仓房编码 | 仓房结构、容量、尺寸等详细信息 |
| `get_grain_temperature` | 查询粮情信息 | 仓房编码, 开始时间, 结束时间 | 粮温（高/低/平）、仓内外温湿度、温度值集合 |
| `get_gas_concentration` | 查询气体信息 | 仓房编码, 开始时间, 结束时间 | 气体浓度（O2, PH3, CO2, N2）、完整气体数据 |

---

## 2. OpenAI Function Definitions (JSON Schema)

以下是用于配置智能体工具 (`tools`) 的 JSON 定义。这些定义已集成到 `app/services/tool_definitions.py` 中，与 T1-T8 工具定义一起提供给 LLM。

**实际使用**：这些函数定义通过 `AgentService.tool_map` 映射到 `GrainTools` 类的对应方法，由 LLM 根据用户意图自动调用。

```json
[
  {
    "type": "function",
    "function": {
      "name": "get_connected_silos",
      "description": "获取当前所有接入智能体的粮仓清单（编码、长名、短名）。",
      "parameters": {
        "type": "object",
        "properties": {},
        "required": []
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_warehouse_info",
      "description": "根据仓房编码查询仓房的详细信息，包括结构、容量和尺寸等。",
      "parameters": {
        "type": "object",
        "properties": {
          "house_code": {
            "type": "string",
            "description": "仓房编码"
          }
        },
        "required": ["house_code"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_grain_temperature",
      "description": "查询指定仓房在一段时间内的粮情数据（温度、湿度等）。",
      "parameters": {
        "type": "object",
        "properties": {
          "house_code": {
            "type": "string",
            "description": "仓房编码"
          },
          "start_time": {
            "type": "string",
            "description": "查询开始时间，格式例如 '2024-01-01 00:00:00'"
          },
          "end_time": {
            "type": "string",
            "description": "查询结束时间，格式例如 '2024-01-01 23:59:59'"
          }
        },
        "required": ["house_code", "start_time", "end_time"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_gas_concentration",
      "description": "查询指定仓房在一段时间内的气体浓度数据（氧气、磷化氢、二氧化碳、氮气等）。",
      "parameters": {
        "type": "object",
        "properties": {
          "house_code": {
            "type": "string",
            "description": "仓房编码"
          },
          "start_time": {
            "type": "string",
            "description": "查询开始时间，格式例如 '2024-01-01 00:00:00'"
          },
          "end_time": {
            "type": "string",
            "description": "查询结束时间，格式例如 '2024-01-01 23:59:59'"
          }
        },
        "required": ["house_code", "start_time", "end_time"]
      }
    }
  }
]
```

---

## 3. Pydantic Models (Python)

用于后端开发的数据模型定义。这些模型定义在 `app/models/domain.py` 中，与以下定义保持一致。

**实现位置**：
- `WarehouseInfo`: `app/models/domain.py` (第33-64行)
- `GrainTempData`: `app/models/domain.py` (第67-82行)
- `GasConcentrationData`: `app/models/domain.py` (第85-100行)

**返回格式**：
- `WMSClient` 方法返回 Pydantic 模型实例或列表（`List[GrainTempData]`）
- `GrainTools` 方法返回字典格式（`Dict[str, Any]`），通过 `model_dump()` 转换

```python
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. 仓房信息 ---

class WarehouseInfo(BaseModel):
    house_code: str = Field(..., description="仓房编码")
    house_name: str = Field(..., description="仓房名称")
    depot_name: str = Field(..., description="库点名称")
    
    # 新增: 实际接口返回的字段
    grain_nature: Optional[str] = Field(None, description="储粮性质")
    variety: Optional[str] = Field(None, description="品种")
    
    # 以下字段在实际接口中可能缺失，改为 Optional 或提供默认值
    house_type_name: Optional[str] = Field("平房仓", description="仓房类型名称")
    construction_year: Optional[str] = Field("", description="建设年代")
    
    # 结构信息
    structure_wall: Optional[str] = Field(None, description="仓房结构名称_墙体")
    structure_roof: Optional[str] = Field(None, description="仓房结构名称_屋顶")
    structure_floor: Optional[str] = Field(None, description="仓房结构名称_地面")
    
    # 容量信息
    design_capacity: float = Field(0.0, description="设计仓容")
    authorized_capacity: float = Field(0.0, description="核定仓容")
    
    # 尺寸信息 (仓外)
    outer_length: Optional[float] = Field(None, description="仓外长")
    outer_width: Optional[float] = Field(None, description="仓外宽")
    outer_eaves_height: Optional[float] = Field(None, description="仓外檐高")
    outer_top_height: Optional[float] = Field(None, description="仓外顶高")
    outer_silo_diameter: Optional[float] = Field(None, description="仓外筒仓外径")
    outer_wall_area: Optional[float] = Field(None, description="仓外外墙面积")
    
    # 尺寸信息 (仓内)
    inner_length: Optional[float] = Field(None, description="仓内长")
    inner_width: Optional[float] = Field(None, description="仓内宽")
    inner_eaves_height: Optional[float] = Field(None, description="仓内檐高")
    inner_silo_diameter: Optional[float] = Field(None, description="仓内筒仓内径")
    inner_volume: Optional[float] = Field(None, description="仓内体积")
    
    actual_grain_height: Optional[float] = Field(None, description="实际装粮线高")


# --- 2. 粮情信息 ---

class GrainTempData(BaseModel):
    house_code: Optional[str] = Field(None, description="仓房编码")
    house_name: Optional[str] = Field(None, description="仓房名称")
    depot_name: Optional[str] = Field(None, description="库点名称")
    check_time: str = Field(..., description="测温时间")
    
    max_temp: float = Field(0.0, description="最高粮温")
    min_temp: float = Field(0.0, description="最低粮温")
    avg_temp: float = Field(0.0, description="平均粮温")
    
    indoor_temp: Optional[float] = Field(0.0, description="仓内温度")
    indoor_humidity: Optional[float] = Field(0.0, description="仓内湿度")
    outdoor_temp: Optional[float] = Field(0.0, description="仓外温度")
    outdoor_humidity: Optional[float] = Field(0.0, description="仓外湿度")
    
    # 格式: "27.7,1,1,1|25.1,1,1,2" (温度,层,行,列)
    temp_values: str = Field("", description="温度值集合")

class GrainTempResponse(BaseModel):
    data: List[GrainTempData]


# --- 3. 气体信息 ---

class GasConcentrationData(BaseModel):
    house_code: Optional[str] = Field(None, description="仓房编码")
    house_name: Optional[str] = Field(None, description="仓房名称")
    depot_name: Optional[str] = Field(None, description="库点名称")
    grain_nature: str = Field("", description="储粮性质")
    variety: str = Field("", description="品种")
    check_time: str = Field(..., description="检测时间")
    sample_points: int = Field(0, description="取样点数量")
    
    avg_o2: Optional[float] = Field(0.0, description="氧气浓度(平均)")
    avg_ph3: Optional[float] = Field(0.0, description="磷化氢浓度(平均)")
    avg_n2: Optional[float] = Field(0.0, description="氮气浓度(平均)")
    avg_co2: Optional[float] = Field(0.0, description="二氧化碳浓度(平均)")
    avg_other: Optional[float] = Field(0.0, description="其他气体浓度(平均)")
    
    # 格式: "1:0.0,0.20,0.06,0.75|..."
    full_gas_data: str = Field("", description="完整气体数据")

class GasConcentrationResponse(BaseModel):
    data: List[GasConcentrationData]
```

---

## 4. 接口实现说明

### 4.1 实现位置

| 接口 | WMSClient 方法 | GrainTools 方法 | 返回类型 |
|:---|:---|:---|:---|
| `get_warehouse_info` | `wms_client.py:18` | `tools.py:322` | `Dict[str, Any]` |
| `get_grain_temperature` | `wms_client.py:41` | `tools.py:326` | `Dict[str, Any]` |
| `get_gas_concentration` | `wms_client.py:77` | `tools.py:332` | `Dict[str, Any]` |

### 4.2 参数类型转换

`GrainTools` 方法接收字符串格式的时间参数（`start_time`, `end_time`），通过 `_parse_dt()` 方法转换为 `datetime` 对象后调用 `WMSClient` 方法。

**时间格式支持**：
- `"%Y-%m-%d %H:%M:%S"` (例如: `"2024-01-01 00:00:00"`)
- `"%Y-%m-%dT%H:%M:%S"` (ISO 格式)
- ISO 8601 格式

### 4.3 返回数据格式

`GrainTools` 方法的返回格式：

**get_warehouse_info**:
```python
{
    "house_code": "1",
    "house_name": "1号仓",
    "depot_name": "中央储备粮某直属库",
    # ... 其他字段
}
```

**get_grain_temperature**:
```python
{
    "house_code": "1",
    "start_time": "2024-01-01 00:00:00",
    "end_time": "2024-01-01 23:59:59",
    "data": [
        {
            "house_name": "1号仓",
            "depot_name": "中央储备粮某直属库",
            "check_time": "2024-01-01 00:00:00",
            "max_temp": 28.5,
            "min_temp": 25.2,
            "avg_temp": 26.8,
            # ... 其他字段
        },
        # ... 更多数据点
    ]
}
```

**get_gas_concentration**:
```python
{
    "house_code": "1",
    "start_time": "2024-01-01 00:00:00",
    "end_time": "2024-01-01 23:59:59",
    "data": [
        {
            "house_name": "1号仓",
            "depot_name": "中央储备粮某直属库",
            "check_time": "2024-01-01 00:00:00",
            "avg_o2": 20.9,
            "avg_ph3": 0.0,
            # ... 其他字段
        },
        # ... 更多数据点
    ]
}
```

---

## 5. 与 T1-T8 工具的关系

这些 WMS 标准接口是 T1-T8 工具的基础数据源：

- **T1 (inspection)**: 调用 `get_grain_temperature` 获取数据后进行巡检分析
- **T2 (extraction)**: 直接调用 `get_grain_temperature` 和 `get_gas_concentration` 提取数据
- **T3 (analysis)**: 调用 `get_grain_temperature` 获取数据后进行深度分析
- **T4/T5 (comparison)**: 调用 `get_grain_temperature` 获取多时间点/多仓数据后进行对比
- **T7 (visualization)**: 调用 `get_grain_temperature` 获取数据后生成图表
- **T8 (report)**: 调用 `get_warehouse_info` 和 `get_grain_temperature` 获取数据后生成报告

所有工具通过 LLM Function Calling 机制被 Agent 自动调度，无需外部系统直接调用。
