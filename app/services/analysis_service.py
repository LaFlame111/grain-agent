from typing import List, Dict, Any
from app.models.domain import Reading
from app.models.schemas import AnalysisResult
import statistics

class AnalysisService:
    """粮情分析服务 - 基于传感器数据进行风险评估"""
    
    # 粮食储藏温度标准（参考值）
    TEMP_THRESHOLDS = {
        "safe_max": 25.0,      # 安全上限
        "warning": 28.0,       # 警告阈值
        "danger": 30.0,        # 危险阈值
    }
    
    HUMIDITY_THRESHOLDS = {
        "safe_max": 60.0,      # 安全上限
        "warning": 65.0,       # 警告阈值
        "danger": 70.0,        # 危险阈值
    }
    
    def analyze_temperature(self, silo_id: str, readings: List[Reading]) -> AnalysisResult:
        """分析粮温数据，识别风险点"""
        
        # 过滤出温度读数
        temp_readings = [r for r in readings if r.type == "temperature"]
        humidity_readings = [r for r in readings if r.type == "humidity"]
        
        if not temp_readings:
            return AnalysisResult(
                silo_id=silo_id,
                analysis_type="temperature",
                findings=["无温度数据"],
                score=0.0
            )
        
        # 按传感器分组统计
        sensor_stats = self._calculate_sensor_statistics(temp_readings)
        
        # 分析发现
        findings = []
        risk_level = "normal"
        score = 100.0
        
        # 检查每个传感器的温度
        hotspots = []
        for sensor_id, stats in sensor_stats.items():
            avg_temp = stats["avg"]
            max_temp = stats["max"]
            
            if max_temp >= self.TEMP_THRESHOLDS["danger"]:
                hotspots.append(f"{sensor_id}: 最高温度 {max_temp:.1f}°C (危险)")
                risk_level = "danger"
                score -= 30
            elif max_temp >= self.TEMP_THRESHOLDS["warning"]:
                hotspots.append(f"{sensor_id}: 最高温度 {max_temp:.1f}°C (警告)")
                if risk_level == "normal":
                    risk_level = "warning"
                score -= 15
            elif avg_temp >= self.TEMP_THRESHOLDS["safe_max"]:
                hotspots.append(f"{sensor_id}: 平均温度 {avg_temp:.1f}°C (偏高)")
                score -= 5
        
        # 整体温度统计
        all_temps = [r.value for r in temp_readings]
        overall_avg = statistics.mean(all_temps)
        overall_max = max(all_temps)
        overall_min = min(all_temps)
        temp_std = statistics.stdev(all_temps) if len(all_temps) > 1 else 0
        
        findings.append(f"整体平均温度: {overall_avg:.1f}°C")
        findings.append(f"温度范围: {overall_min:.1f}°C ~ {overall_max:.1f}°C")
        findings.append(f"温度标准差: {temp_std:.2f}°C")
        
        # 温度分布不均匀检测
        if temp_std > 3.0:
            findings.append(f"⚠️ 温度分布不均匀（标准差 {temp_std:.2f}°C），可能存在热点")
            score -= 10
        
        # 添加热点信息
        if hotspots:
            findings.append("🔥 检测到以下热点:")
            findings.extend([f"  - {h}" for h in hotspots])
        else:
            findings.append("✓ 未检测到明显热点")
        
        # 湿度分析
        if humidity_readings:
            humidity_values = [r.value for r in humidity_readings]
            avg_humidity = statistics.mean(humidity_values)
            findings.append(f"平均湿度: {avg_humidity:.1f}%")
            
            if avg_humidity >= self.HUMIDITY_THRESHOLDS["warning"]:
                findings.append(f"⚠️ 湿度偏高 ({avg_humidity:.1f}%)，可能导致霉变风险")
                score -= 10
        
        # 确保分数在0-100之间
        score = max(0.0, min(100.0, score))
        
        # 根据风险等级映射到标准值（low/medium/high）
        risk_level_mapping = {
            "normal": "low",
            "warning": "medium",
            "danger": "high"
        }
        standardized_risk_level = risk_level_mapping.get(risk_level, "low")
        
        return AnalysisResult(
            silo_id=silo_id,
            analysis_type="temperature",
            findings=findings,
            risk_level=standardized_risk_level,
            score=score
        )
    
    def _calculate_sensor_statistics(self, readings: List[Reading]) -> Dict[str, Dict[str, float]]:
        """计算每个传感器的统计数据"""
        sensor_data = {}
        
        for reading in readings:
            if reading.sensor_id not in sensor_data:
                sensor_data[reading.sensor_id] = []
            sensor_data[reading.sensor_id].append(reading.value)
        
        stats = {}
        for sensor_id, values in sensor_data.items():
            stats[sensor_id] = {
                "avg": statistics.mean(values),
                "max": max(values),
                "min": min(values),
                "count": len(values)
            }
        
        return stats

