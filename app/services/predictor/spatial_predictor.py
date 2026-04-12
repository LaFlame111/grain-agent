"""
空间热点预测器 - P1 核心功能

对粮仓内各传感器点位进行独立建模，识别：
1. 当前热点位置（最高温点位）
2. 潜在热点（温度上升速率异常的点位）
3. 未来 N 天各点位温度预测

使用示例：
    >>> from app.services.predictor.spatial_predictor import SpatialTempPredictor
    >>> predictor = SpatialTempPredictor()
    >>> sensors = predictor.parse_temp_values(series)
    >>> hotspots = predictor.identify_hotspots(sensors)
    >>> predictions = predictor.predict_spatial(sensors, prediction_days=3)
"""

import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.domain import GrainTempData
import logging

logger = logging.getLogger(__name__)


class SensorReading:
    """单个传感器的时间序列数据"""

    def __init__(self, layer: int, row: int, col: int):
        self.layer = layer
        self.row = row
        self.col = col
        self.times: List[datetime] = []
        self.temps: List[float] = []

    @property
    def sensor_id(self) -> str:
        return f"L{self.layer}R{self.row}C{self.col}"

    @property
    def latest_temp(self) -> Optional[float]:
        return self.temps[-1] if self.temps else None

    def add_reading(self, time: datetime, temp: float):
        self.times.append(time)
        self.temps.append(temp)


class SpatialTempPredictor:
    """空间温度预测器"""

    def parse_temp_values(
        self, series: List[GrainTempData]
    ) -> Dict[str, SensorReading]:
        """
        解析 temp_values 字符串，构建各传感器时间序列

        格式: "27.7,1,1,1|25.1,1,1,2" → (温度,层,行,列)

        Args:
            series: GrainTempData 时间序列列表

        Returns:
            {sensor_id: SensorReading} 字典
        """
        sensors: Dict[str, SensorReading] = {}

        for record in series:
            try:
                check_time = datetime.strptime(record.check_time, "%Y-%m-%d %H:%M:%S")
            except:
                continue

            parts = [p for p in (record.temp_values or "").split("|") if p.strip()]
            for p in parts:
                try:
                    val_s, layer_s, row_s, col_s = [x.strip() for x in p.split(",")]
                    layer, row, col = int(layer_s), int(row_s), int(col_s)
                    temp = float(val_s)

                    sensor_key = f"L{layer}R{row}C{col}"
                    if sensor_key not in sensors:
                        sensors[sensor_key] = SensorReading(layer, row, col)

                    sensors[sensor_key].add_reading(check_time, temp)
                except Exception as e:
                    logger.debug(f"解析传感器数据失败: {p}, 错误: {e}")
                    continue

        logger.info(f"解析得到 {len(sensors)} 个传感器的时间序列数据")
        return sensors

    def identify_hotspots(
        self,
        sensors: Dict[str, SensorReading],
        threshold_temp: float = 28.0,
        threshold_rate: float = 0.5,  # °C/day
    ) -> Dict[str, Any]:
        """
        识别当前热点和潜在热点

        Args:
            sensors: 各传感器数据字典
            threshold_temp: 温度阈值（°C）
            threshold_rate: 升温速率阈值（°C/day）

        Returns:
            {
                "current_hotspots": [...],    # 当前高温点
                "emerging_hotspots": [...],   # 新兴热点
                "max_temp_location": {...}    # 最高温位置
            }
        """
        current_hotspots = []
        emerging_hotspots = []
        max_temp = -999.0
        max_location = None

        for sensor_id, reading in sensors.items():
            if not reading.temps:
                continue

            latest_temp = reading.latest_temp

            # 更新最高温位置
            if latest_temp > max_temp:
                max_temp = latest_temp
                max_location = {
                    "sensor_id": sensor_id,
                    "layer": reading.layer,
                    "row": reading.row,
                    "col": reading.col,
                    "temp": round(latest_temp, 1),
                }

            # 当前高温点
            if latest_temp >= threshold_temp:
                current_hotspots.append(
                    {
                        "sensor_id": sensor_id,
                        "layer": reading.layer,
                        "row": reading.row,
                        "col": reading.col,
                        "current_temp": round(latest_temp, 1),
                        "severity": "critical" if latest_temp >= 30 else "warning",
                    }
                )

            # 新兴热点：近期升温速率异常
            if len(reading.temps) >= 3:
                recent_temps = np.array(reading.temps[-3:])
                recent_times_days = np.arange(3, dtype=float)

                # 线性拟合计算斜率
                try:
                    coeffs = np.polyfit(recent_times_days, recent_temps, deg=1)
                    rate = coeffs[0]  # °C/检测周期

                    # 假设平均检测间隔 1 天，转换为 °C/day
                    avg_interval = 1.0
                    if len(reading.times) >= 2:
                        intervals = [
                            (reading.times[i] - reading.times[i - 1]).total_seconds()
                            / 86400
                            for i in range(1, min(4, len(reading.times)))
                        ]
                        avg_interval = np.mean(intervals) if intervals else 1.0

                    rate_per_day = rate / avg_interval if avg_interval > 0 else 0.0

                    if rate_per_day > threshold_rate and latest_temp < threshold_temp:
                        emerging_hotspots.append(
                            {
                                "sensor_id": sensor_id,
                                "layer": reading.layer,
                                "row": reading.row,
                                "col": reading.col,
                                "current_temp": round(latest_temp, 1),
                                "rate": round(rate_per_day, 2),
                                "warning": f"升温速率 {rate_per_day:.2f}°C/天，可能萌发热点",
                            }
                        )
                except:
                    continue

        logger.info(
            f"识别到 {len(current_hotspots)} 个当前高温点, "
            f"{len(emerging_hotspots)} 个潜在热点"
        )

        return {
            "current_hotspots": current_hotspots,
            "emerging_hotspots": emerging_hotspots,
            "max_temp_location": max_location,
        }

    def predict_spatial(
        self, sensors: Dict[str, SensorReading], prediction_days: int = 3
    ) -> List[Dict[str, Any]]:
        """
        对各传感器进行独立预测（轻量级 Layer 1）

        Args:
            sensors: 各传感器数据字典
            prediction_days: 预测天数

        Returns:
            [{sensor_id, layer, row, col, current_temp, predicted_temp, trend}, ...]
            按预测温度降序排序
        """
        predictions = []

        for sensor_id, reading in sensors.items():
            if len(reading.temps) < 7:
                # 数据不足，跳过
                continue

            try:
                vals = np.array(reading.temps, dtype=float)
                times = np.array(
                    [
                        (t - reading.times[0]).total_seconds() / 86400
                        for t in reading.times
                    ]
                )

                # 使用简单的线性回归预测（轻量级）
                coeffs = np.polyfit(times, vals, deg=1)
                last_t = times[-1]
                future_t = last_t + prediction_days
                pred_temp = np.polyval(coeffs, future_t)
                rate = coeffs[0]  # °C/day

                predictions.append(
                    {
                        "sensor_id": sensor_id,
                        "layer": reading.layer,
                        "row": reading.row,
                        "col": reading.col,
                        "current_temp": round(reading.latest_temp, 1),
                        "predicted_temp": round(float(pred_temp), 1),
                        "daily_rate": round(rate, 3),
                        "trend": "上升"
                        if rate > 0.05
                        else ("下降" if rate < -0.05 else "稳定"),
                    }
                )
            except Exception as e:
                logger.debug(f"传感器 {sensor_id} 预测失败: {e}")
                continue

        # 按预测温度降序排序
        predictions.sort(key=lambda x: x["predicted_temp"], reverse=True)

        logger.info(f"完成 {len(predictions)} 个传感器的空间预测")
        return predictions
