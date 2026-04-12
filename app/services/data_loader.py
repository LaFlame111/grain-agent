"""
数据加载模块

负责从 JSON 文件加载真实粮情数据，并建立索引以加速查询。
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from app.models.domain import GrainTempData

logger = logging.getLogger(__name__)


class DataLoader:
    """数据加载器：从 JSON 文件加载真实粮情数据"""
    
    def __init__(self, data_file: Optional[Path] = None):
        """
        初始化数据加载器
        
        Args:
            data_file: 数据文件路径，默认为项目根目录下的 data/grain_data_wms_format.json
        """
        if data_file is None:
            # 默认路径：项目根目录下 data/grain_data_wms_format.json
            base_dir = Path(__file__).resolve().parent.parent.parent
            data_file = base_dir.parent / "data" / "grain_data_wms_format.json"
        
        self.data_file = Path(data_file)
        self.raw_data: List[Dict] = []
        self.indexed_data: Dict[str, List[Dict]] = {}  # 按 house_code 索引
        
    def load(self) -> bool:
        """
        加载数据文件到内存
        
        Returns:
            bool: 加载是否成功
        """
        if not self.data_file.exists():
            logger.error(f"数据文件不存在: {self.data_file}")
            return False
        
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.raw_data = json.load(f)
            
            logger.info(f"成功加载 {len(self.raw_data)} 条粮情数据记录")
            
            # 建立索引：按 house_code 分组
            self._build_index()
            
            return True
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析错误: {e}")
            return False
        except Exception as e:
            logger.error(f"加载数据文件失败: {e}")
            return False
    
    def _build_index(self):
        """建立数据索引：按 house_code 分组"""
        self.indexed_data = {}

        for record in self.raw_data:
            keys = []
            # 优先使用记录中的 house_code 字段（WMS 完整编码）
            raw_code = record.get("house_code", "")
            if raw_code:
                keys.append(raw_code)
            # 同时从 house_name 中提取仓号（如 "15号仓" -> "15"）
            house_name = record.get("house_name", "")
            name_code = self._extract_house_code(house_name)
            if name_code and name_code not in keys:
                keys.append(name_code)

            for house_code in keys:
                if house_code not in self.indexed_data:
                    self.indexed_data[house_code] = []
                self.indexed_data[house_code].append(record)
        
        # 对每个仓号的数据按时间排序
        for house_code in self.indexed_data:
            self.indexed_data[house_code].sort(
                key=lambda x: x.get("check_time", "")
            )
        
        logger.info(f"建立索引完成，共 {len(self.indexed_data)} 个仓号")
    
    def _extract_house_code(self, house_name: str) -> Optional[str]:
        """
        从仓房名称中提取仓号
        
        Args:
            house_name: 仓房名称，如 "15号仓"
        
        Returns:
            仓号字符串，如 "15"，如果无法提取则返回 None
        """
        if not house_name:
            return None
        
        import re
        # 匹配 "15号仓" 或 "15" 等格式
        match = re.search(r'(\d+)', house_name)
        if match:
            return match.group(1)
        return None
    
    def query(
        self,
        house_code: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[GrainTempData]:
        """
        查询粮温数据
        
        Args:
            house_code: 仓号，如 "15"
            start_time: 查询开始时间（可选）
            end_time: 查询结束时间（可选）
        
        Returns:
            GrainTempData 列表
        """
        if not self.indexed_data:
            logger.warning("数据未加载，返回空列表")
            return []
        
        # 从索引中获取该仓号的数据
        records = self.indexed_data.get(house_code, [])
        
        if not records:
            logger.debug(f"仓号 {house_code} 无数据")
            return []
        
        # 如果指定了时间范围，进行过滤
        if start_time or end_time:
            filtered_records = []
            for record in records:
                check_time_str = record.get("check_time", "")
                if not check_time_str:
                    continue
                
                try:
                    check_time = datetime.strptime(check_time_str, "%Y-%m-%d %H:%M:%S")
                    
                    # 时间范围过滤
                    if start_time and check_time < start_time:
                        continue
                    if end_time and check_time > end_time:
                        continue
                    
                    filtered_records.append(record)
                except ValueError:
                    logger.warning(f"无法解析时间格式: {check_time_str}")
                    continue
            
            records = filtered_records
        
        # 转换为 GrainTempData 对象
        result = []
        for record in records:
            try:
                grain_data = GrainTempData(
                    house_name=record.get("house_name", ""),
                    depot_name=record.get("depot_name", ""),
                    check_time=record.get("check_time", ""),
                    max_temp=float(record.get("max_temp", 0.0)),
                    min_temp=float(record.get("min_temp", 0.0)),
                    avg_temp=float(record.get("avg_temp", 0.0)),
                    indoor_temp=float(record.get("indoor_temp", 0.0)),
                    indoor_humidity=float(record.get("indoor_humidity", 0.0)),
                    outdoor_temp=float(record.get("outdoor_temp", 0.0)),
                    outdoor_humidity=float(record.get("outdoor_humidity", 0.0)),
                    temp_values=record.get("temp_values", "")
                )
                result.append(grain_data)
            except Exception as e:
                logger.warning(f"转换数据记录失败: {e}, record: {record}")
                continue
        
        logger.debug(f"查询仓号 {house_code}，返回 {len(result)} 条记录")
        return result
    
    def get_warehouse_info(self, house_code: str) -> Optional[Dict]:
        """
        获取仓房基本信息（从数据中提取）
        
        Args:
            house_code: 仓号
        
        Returns:
            仓房信息字典，如果无数据则返回 None
        """
        if not self.indexed_data:
            return None
        
        records = self.indexed_data.get(house_code, [])
        if not records:
            return None
        
        # 取第一条记录提取基本信息
        first_record = records[0]
        return {
            "house_code": house_code,
            "house_name": first_record.get("house_name", f"{house_code}号仓"),
            "depot_name": first_record.get("depot_name", "中央储备粮某直属库")
        }
    
    def get_all_house_codes(self) -> List[str]:
        """
        获取所有可用的仓号列表
        
        Returns:
            仓号列表
        """
        return list(self.indexed_data.keys())


# 全局数据加载器实例
_data_loader: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    """
    获取全局数据加载器实例（单例模式）
    
    Returns:
        DataLoader 实例
    """
    global _data_loader
    if _data_loader is None:
        _data_loader = DataLoader()
        if not _data_loader.load():
            logger.warning("数据加载失败，将使用 Mock 数据")
    return _data_loader
