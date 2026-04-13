from typing import List, Optional
from datetime import datetime, timedelta
import random
import logging
import httpx
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from datetime import datetime, timedelta
from app.models.domain import (
    Warehouse,
    Silo,
    Sensor,
    Reading,
    WarehouseInfo,
    GrainTempData,
    GasConcentrationData,
)
from app.services.data_loader import get_data_loader
from app.core.wms_endpoints import (
    WMS_ENDPOINT_WAREHOUSE_LIST,
    WMS_ENDPOINT_WAREHOUSE_INFO,
    WMS_ENDPOINT_GRAIN_TEMPERATURE,
    WMS_ENDPOINT_GAS_CONCENTRATION,
    WMS_API_TIMEOUT,
)

logger = logging.getLogger(__name__)


class WMSClient:
    def __init__(self):
        # 本地测试数据加载器（本地 JSON 兜底）
        self.data_loader = get_data_loader()
        self.use_real_data = len(self.data_loader.raw_data) > 0

        # V008: 启用 HTTP 客户端
        self.client = httpx.Client(timeout=WMS_API_TIMEOUT)

        if self.use_real_data:
            logger.info(
                f"WMSClient 已加载本地测试数据 {len(self.data_loader.raw_data)} 条记录"
            )
        else:
            logger.warning("WMSClient 未加载到本地测试数据")
        logger.info("WMSClient 已初始化，支持真实 HTTP API 模式")

    def _parse_api_date(self, date_str: str) -> str:
        """
        API 返回的时间格式可能是 '2026/1/4 9:41:24'
        需要转换为标准格式 '2026-01-04 09:41:24'
        """
        if not date_str:
            return ""
        try:
            # 尝试解析并重新格式化
            dt = datetime.strptime(date_str.replace("/", "-"), "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return date_str

    def resolve_house_code(self, silo_id: str) -> str:
        """
        将简写的仓号（如 "P1", "15"）解析为完整的 WMS house_code。
        """
        # 如果看起来已经是完整编码，直接返回
        if len(silo_id) > 10:
            return silo_id

        # 硬编码映射优先（含本地 Excel 导入的仓房），避免被远程 API 误匹配
        test_mapping = {
            "P1": "91620702MADKWU312X01001",
            "Q1": "91620702MADKWU312X01012",
            # 本地 Excel 导入的仓房
            "15": "ZMD_ZMDZSZK_015",
            "15号仓": "ZMD_ZMDZSZK_015",
            "Z15": "ZMD_ZMDZSZK_015",
        }
        if silo_id in test_mapping:
            return test_mapping[silo_id]
        if silo_id.upper() in test_mapping:
            return test_mapping[silo_id.upper()]

        # V008: 再从接入列表接口获取实时映射
        try:
            connected_silos = self.get_connected_silos()
            for silo in connected_silos:
                if silo_id.upper() == silo.get("short_name", "").upper():
                    return silo.get("house_code")
                if silo_id.upper() in silo.get("house_name", "").upper():
                    return silo.get("house_code")
        except Exception:
            pass

        # 尝试从本地加载器中查找映射
        house_codes = self.data_loader.get_all_house_codes()
        # 简单匹配：看 silo_id 是否在某个 code 里，或者 code 对应的 name 包含 silo_id
        for code in house_codes:
            if silo_id.lower() in code.lower():
                return code
            info = self.data_loader.get_warehouse_info(code)
            if info and silo_id.lower() in info.get("house_name", "").lower():
                return code

        # 如果没找到，返回原值（尝试直接调用 API）
        return silo_id

    def get_connected_silos(self) -> List[Dict[str, str]]:
        """
        V008: 获取接入仓房列表（WMS API + 本地 Excel 导入的仓房）
        """
        silos: List[Dict[str, str]] = []

        # 1. 尝试从 WMS API 获取
        try:
            logger.info("从 WMS 获取接入仓房列表...")
            response = self.client.get(WMS_ENDPOINT_WAREHOUSE_LIST)
            if response.status_code == 200:
                silos = response.json() or []
        except Exception as e:
            logger.warning(f"获取接入列表失败: {e}")
            # 使用硬编码兜底
            silos = [
                {
                    "house_code": "91620702MADKWU312X01001",
                    "house_name": "西北库区 P1",
                    "short_name": "P1",
                },
                {
                    "house_code": "91620702MADKWU312X01012",
                    "house_name": "西北库区 Q1",
                    "short_name": "Q1",
                },
            ]

        # 2. 合并本地 DataLoader 中的仓房（Excel 导入等）
        existing_codes = {s.get("house_code") for s in silos}
        for code in self.data_loader.get_all_house_codes():
            if code in existing_codes:
                continue
            # 跳过纯数字短码（如 "15"，这是 house_name 提取出的索引，不是真实 code）
            if code.isdigit():
                continue
            info = self.data_loader.get_warehouse_info(code)
            if info:
                silos.append(
                    {
                        "house_code": code,
                        "house_name": info.get("house_name", code),
                        "short_name": info.get("house_name", code),
                        "data_source": "local",
                    }
                )
                existing_codes.add(code)
                logger.info(
                    f"本地仓房已加入接入列表: {code} ({info.get('house_name')})"
                )

        return silos

    def get_warehouse_info(self, house_code: str) -> WarehouseInfo:
        """
        获取仓房基本信息 (V008: 通过真实 API 获取)
        """
        try:
            logger.info(f"正在从 WMS API 获取仓房信息: {house_code}")
            response = self.client.get(
                WMS_ENDPOINT_WAREHOUSE_INFO, params={"house_code": house_code}
            )

            if response.status_code == 200:
                data = response.json()
                if data and data.get("house_code"):
                    logger.info(f"成功获取 API 仓房数据: {data.get('house_name')}")
                    return WarehouseInfo(
                        house_code=data.get("house_code", house_code),
                        house_name=data.get("house_name", f"{house_code}号仓"),
                        depot_name=data.get("depot_name", "WMS 系统库区"),
                        grain_nature=data.get("grain_nature"),
                        variety=data.get("variety"),
                        house_type_name=data.get("house_type_name", "未知类型"),
                        construction_year=data.get("construction_year", ""),
                        design_capacity=data.get("design_capacity", 0.0),
                        authorized_capacity=data.get("authorized_capacity", 0.0),
                        structure_wall=data.get("structure_wall", ""),
                        structure_roof=data.get("structure_roof", ""),
                        structure_floor=data.get("structure_floor", ""),
                        outer_length=data.get("outer_length", 0.0),
                        outer_width=data.get("outer_width", 0.0),
                        outer_eaves_height=data.get("outer_eaves_height", 0.0),
                        inner_length=data.get("inner_length", 0.0),
                        inner_width=data.get("inner_width", 0.0),
                        inner_eaves_height=data.get("inner_eaves_height", 0.0),
                        actual_grain_height=data.get("actual_grain_height", 0.0),
                    )
            logger.warning(
                f"WMS API 返回异常 (Status: {response.status_code})，尝试回退到本地数据"
            )
        except Exception as e:
            logger.error(f"访问 WMS API 失败: {e}，尝试回退到本地数据")

        # 兜底：尝试从本地 JSON 加载
        try:
            info_dict = self.data_loader.get_warehouse_info(house_code)
            if info_dict:
                # 补全缺失的必填字段（如果本地数据也不全）
                if "house_name" not in info_dict:
                    info_dict["house_name"] = f"{house_code}号仓"
                if "depot_name" not in info_dict:
                    info_dict["depot_name"] = "本地模拟库区"
                return WarehouseInfo(**info_dict)
        except Exception:
            pass

        # 最终 Mock 兜底
        return WarehouseInfo(
            house_code=house_code,
            house_name=f"{house_code}号仓",
            depot_name="本地模拟库区",
            house_type_name="平房仓",
            construction_year="2010",
            design_capacity=5000.0,
            authorized_capacity=4800.0,
        )

    def get_grain_temperature(
        self, house_code: str, start_time: datetime, end_time: datetime
    ) -> List[GrainTempData]:
        """
        获取粮温数据 (V008: 通过真实 API 获取)
        """
        # 获取仓房列表以便补全名称
        silos_map = {s["house_code"]: s for s in self.get_connected_silos()}
        silo_meta = silos_map.get(house_code, {})

        try:
            params = {
                "house_code": house_code,
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            logger.info(f"正在从 WMS API 获取粮温数据: {house_code}")
            response = self.client.get(WMS_ENDPOINT_GRAIN_TEMPERATURE, params=params)

            if response.status_code == 200:
                api_results = response.json()
                if not isinstance(api_results, list):
                    logger.warning(f"WMS API 粮温接口返回异常数据格式: {api_results}")
                    api_results = []

                if len(api_results) > 0:
                    logger.info(f"成功从 API 获取到 {len(api_results)} 条粮温记录")
                    formatted_results = []
                    for item in api_results:
                        formatted_results.append(
                            GrainTempData(
                                house_code=item.get("house_code", house_code),
                                house_name=item.get("house_name")
                                or silo_meta.get("house_name")
                                or f"{house_code}号仓",
                                depot_name=item.get("depot_name") or "西北库区",
                                check_time=self._parse_api_date(
                                    item.get("check_time", "")
                                ),
                                max_temp=item.get("max_temp")
                                if item.get("max_temp") is not None
                                else 0.0,
                                min_temp=item.get("min_temp")
                                if item.get("min_temp") is not None
                                else 0.0,
                                avg_temp=item.get("avg_temp")
                                if item.get("avg_temp") is not None
                                else 0.0,
                                indoor_temp=item.get("indoor_temp")
                                if item.get("indoor_temp") is not None
                                else 0.0,
                                indoor_humidity=item.get("indoor_humidity")
                                if item.get("indoor_humidity") is not None
                                else 0.0,
                                outdoor_temp=item.get("outdoor_temp")
                                if item.get("outdoor_temp") is not None
                                else 0.0,
                                outdoor_humidity=item.get("outdoor_humidity")
                                if item.get("outdoor_humidity") is not None
                                else 0.0,
                                temp_values=item.get("temp_values", ""),
                            )
                        )
                    return formatted_results
            logger.warning(
                f"WMS API 粮温接口无数据或异常 (Status: {response.status_code})，尝试回退"
            )
        except Exception as e:
            logger.error(f"访问 WMS 粮温 API 失败: {e}，尝试回退")

        # 兜底：本地 JSON
        return self.data_loader.query(house_code, start_time, end_time)

    def get_gas_concentration(
        self, house_code: str, start_time: datetime, end_time: datetime
    ) -> List[GasConcentrationData]:
        """
        获取气体浓度数据 (V008: 通过真实 API 获取)
        """
        # 获取仓房列表以便补全名称
        silos_map = {s["house_code"]: s for s in self.get_connected_silos()}
        silo_meta = silos_map.get(house_code, {})

        try:
            params = {
                "house_code": house_code,
                "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end_time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            logger.info(f"正在从 WMS API 获取气体浓度: {house_code}")
            response = self.client.get(WMS_ENDPOINT_GAS_CONCENTRATION, params=params)

            if response.status_code == 200:
                api_results = response.json()
                if not isinstance(api_results, list):
                    logger.warning(f"WMS API 气体接口返回异常数据格式: {api_results}")
                    api_results = []

                if len(api_results) > 0:
                    logger.info(f"成功从 API 获取到 {len(api_results)} 条气体记录")
                    formatted_results = []
                    for item in api_results:
                        formatted_results.append(
                            GasConcentrationData(
                                house_code=item.get("house_code", house_code),
                                house_name=item.get("house_name")
                                or silo_meta.get("house_name")
                                or f"{house_code}号仓",
                                depot_name=item.get("depot_name") or "西北库区",
                                grain_nature=item.get("grain_nature") or "",
                                variety=item.get("variety") or "",
                                check_time=self._parse_api_date(
                                    item.get("check_time", "")
                                ),
                                sample_points=item.get("sample_points")
                                if item.get("sample_points") is not None
                                else 0,
                                avg_o2=item.get("avg_o2")
                                if item.get("avg_o2") is not None
                                else 0.0,
                                avg_ph3=item.get("avg_ph3")
                                if item.get("avg_ph3") is not None
                                else 0.0,
                                avg_co2=item.get("avg_co2")
                                if item.get("avg_co2") is not None
                                else 0.0,
                                avg_n2=item.get("avg_n2")
                                if item.get("avg_n2") is not None
                                else 0.0,
                                avg_other=item.get("avg_other")
                                if item.get("avg_other") is not None
                                else 0.0,
                                full_gas_data=item.get("full_gas_data", ""),
                            )
                        )
                    return formatted_results
        except Exception as e:
            logger.error(f"访问 WMS 气体 API 失败: {e}")

        return []  # 气体数据目前无本地 JSON 兜底，直接返回空

    # --- 旧接口 (保留兼容) ---

    def get_warehouse(self, warehouse_id: str) -> Optional[Warehouse]:
        # Mock data
        return Warehouse(
            id=warehouse_id,
            name=f"Mock Warehouse {warehouse_id}",
            silos=[self.get_silo(f"{warehouse_id}-S{i}") for i in range(1, 4)],
        )

    def get_silo(self, silo_id: str) -> Silo:
        # 为1号仓创建更多传感器（模拟真实布局）
        if str(silo_id).startswith("1"):
            sensors = [
                Sensor(
                    id="1-T1",
                    type="temperature",
                    location={"x": 0.0, "y": 0.0, "z": 0.0},
                ),
                Sensor(
                    id="1-T2",
                    type="temperature",
                    location={"x": 5.0, "y": 0.0, "z": 0.0},
                ),
                Sensor(
                    id="1-T3",
                    type="temperature",
                    location={"x": 10.0, "y": 0.0, "z": 0.0},
                ),
                Sensor(
                    id="1-T4",
                    type="temperature",
                    location={"x": 0.0, "y": 5.0, "z": 0.0},
                ),
                Sensor(
                    id="1-T5",
                    type="temperature",
                    location={"x": 5.0, "y": 5.0, "z": 0.0},
                ),
                Sensor(
                    id="1-H1", type="humidity", location={"x": 2.5, "y": 2.5, "z": 0.0}
                ),
            ]
        else:
            sensors = [
                Sensor(
                    id=f"{silo_id}-T1",
                    type="temperature",
                    location={"x": 1.0, "y": 1.0, "z": 1.0},
                ),
                Sensor(
                    id=f"{silo_id}-H1",
                    type="humidity",
                    location={"x": 1.0, "y": 1.0, "z": 1.0},
                ),
            ]

        return Silo(
            id=silo_id,
            name=f"Silo {silo_id}",
            capacity=1000.0,
            current_level=random.uniform(500.0, 900.0),
            sensors=sensors,
        )

    def get_readings(
        self, silo_id: str, start_time: datetime, end_time: datetime
    ) -> List[Reading]:
        """获取传感器读数，为1号仓生成更真实的数据"""
        readings = []
        current = start_time

        # 为1号仓生成特殊的温度模式
        if str(silo_id).startswith("1"):
            while current <= end_time:
                # 温度传感器读数
                for sensor_id in ["1-T1", "1-T2", "1-T3", "1-T4", "1-T5"]:
                    if sensor_id == "1-T3":  # 热点传感器
                        # 热点温度：偏高且有波动
                        temp = self.silo_1_temp_pattern[
                            "hotspot_temp"
                        ] + random.uniform(-1.0, 2.0)
                    else:
                        # 正常温度：基础温度 + 小波动
                        temp = self.silo_1_temp_pattern["base_temp"] + random.uniform(
                            -2.0, 2.0
                        )

                    readings.append(
                        Reading(
                            sensor_id=sensor_id,
                            timestamp=current,
                            value=round(temp, 2),
                            type="temperature",
                        )
                    )

                # 湿度传感器读数
                readings.append(
                    Reading(
                        sensor_id="1-H1",
                        timestamp=current,
                        value=round(random.uniform(55.0, 65.0), 2),  # 湿度稍高
                        type="humidity",
                    )
                )

                current += timedelta(hours=1)
        else:
            # 其他仓的随机数据
            while current <= end_time:
                readings.append(
                    Reading(
                        sensor_id=f"{silo_id}-T1",
                        timestamp=current,
                        value=round(random.uniform(20.0, 30.0), 2),
                        type="temperature",
                    )
                )
                readings.append(
                    Reading(
                        sensor_id=f"{silo_id}-H1",
                        timestamp=current,
                        value=round(random.uniform(40.0, 60.0), 2),
                        type="humidity",
                    )
                )
                current += timedelta(hours=1)

        return readings
