from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

# --- 原始基础模型 (保留用于内部逻辑) ---
class Reading(BaseModel):
    sensor_id: str
    timestamp: datetime
    value: float
    type: str # 'temperature', 'humidity', 'gas'
    quality: str = "ok" # ok, miss, noise

class Sensor(BaseModel):
    id: str
    type: str
    location: Dict[str, float] # {'x': 1.0, 'y': 2.0, 'z': 3.0}

class Silo(BaseModel):
    id: str
    name: str
    capacity: float
    current_level: float
    sensors: List[Sensor] = []

class Warehouse(BaseModel):
    id: str
    name: str
    silos: List[Silo] = []

# --- 新增业务模型 (对应 interface_schema.md) ---

# 1. 仓房信息
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

# 2. 粮情信息
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

# 3. 气体信息
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
    
    # 格式: "1:0.16,20.28,431,0|..."
    full_gas_data: str = Field("", description="完整气体数据")

