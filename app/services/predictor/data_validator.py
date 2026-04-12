"""
数据质量验证器 - P0 改进

提供多层级异常检测：
1. 物理边界检查（-10°C ~ 50°C）
2. 统计离群点检测（IQR 方法）
3. 时间一致性检查（日变化率 < 2°C）
4. 传感器漂移检测（移动窗口偏差）

使用示例：
    >>> from app.services.predictor.data_validator import DataValidator
    >>> vals = np.array([20.0, -50.0, 25.0])  # -50°C 为异常
    >>> times = np.array([0, 1, 2])
    >>> mask, stats = DataValidator.detect_anomalies(vals, times, "medium")
    >>> print(stats)
    {'physical_boundary': 1, 'statistical_outlier': 0, 'rate_violation': 0, 'sensor_drift': 0}
"""

import numpy as np
from typing import Tuple, Dict
import logging

logger = logging.getLogger(__name__)


class DataValidator:
    """粮温数据质量验证器"""

    # 物理约束常量
    PHYSICAL_MIN = -10.0  # 中国粮库实际下限（东北冬季极端情况）
    PHYSICAL_MAX = 50.0  # 物理上限（夏季暴晒极端情况）
    MAX_DAILY_CHANGE = 2.0  # 粮温日最大变化率（°C/day，基于粮堆热惯性）

    @staticmethod
    def detect_anomalies(
        vals: np.ndarray, times: np.ndarray, sensitivity: str = "medium"
    ) -> Tuple[np.ndarray, Dict[str, int]]:
        """
        多层级异常检测

        Args:
            vals: 温度序列（ndarray）
            times: 对应时间戳（相对天数，ndarray）
            sensitivity: 灵敏度（low/medium/high）
                - low: 仅物理边界检查
                - medium: 物理边界 + 时间一致性（默认，用于预测）
                - high: 全部检测（用于告警场景）

        Returns:
            (mask, stats):
                - mask: bool 数组，mask[i]=True 表示有效数据
                - stats: 各类异常计数统计
        """
        n = len(vals)
        if n == 0:
            return np.array([], dtype=bool), {
                "physical_boundary": 0,
                "statistical_outlier": 0,
                "rate_violation": 0,
                "sensor_drift": 0,
            }

        mask = np.ones(n, dtype=bool)
        stats = {
            "physical_boundary": 0,
            "statistical_outlier": 0,
            "rate_violation": 0,
            "sensor_drift": 0,
        }

        # 1. 物理边界检查（P0 改进：收紧到 -10~50°C）
        physical_mask = (vals >= DataValidator.PHYSICAL_MIN) & (
            vals <= DataValidator.PHYSICAL_MAX
        )
        mask &= physical_mask
        stats["physical_boundary"] = int(np.sum(~physical_mask))

        if stats["physical_boundary"] > 0:
            logger.debug(
                f"物理边界检查: 剔除 {stats['physical_boundary']} 个异常点 "
                f"(< {DataValidator.PHYSICAL_MIN}°C 或 > {DataValidator.PHYSICAL_MAX}°C)"
            )

        # 短路：如果没有有效数据，提前返回
        if not np.any(mask):
            return mask, stats

        # 2. 统计离群点检测（IQR 方法，保留热点信号）
        if sensitivity in ("medium", "high"):
            valid_vals = vals[mask]
            if len(valid_vals) >= 4:  # IQR 至少需要 4 个点
                q1, q3 = np.percentile(valid_vals, [25, 75])
                iqr = q3 - q1

                # 根据灵敏度调整阈值
                if sensitivity == "high":
                    k = 1.5  # 标准 IQR
                else:
                    k = 3.0  # 宽松 IQR（保留真实热点）

                lower = q1 - k * iqr
                # 只剔除下界异常，保留上界异常（可能是真实热点）
                # 注意：这里只检查有效数据
                stat_mask_full = np.ones(n, dtype=bool)
                for i in range(n):
                    if mask[i] and vals[i] < lower:
                        stat_mask_full[i] = False
                        stats["statistical_outlier"] += 1

                mask &= stat_mask_full

                if stats["statistical_outlier"] > 0:
                    logger.debug(
                        f"统计离群点检测: 剔除 {stats['statistical_outlier']} 个下界异常点 (< {lower:.1f}°C)"
                    )

        # 3. 时间一致性检查（日变化率 < 2°C/day）
        if (
            sensitivity in ("medium", "high")
            and len(times) == len(vals)
            and len(vals) > 1
        ):
            for i in range(1, n):
                if not mask[i] or not mask[i - 1]:
                    continue

                dt = times[i] - times[i - 1]
                if dt > 0:
                    rate = abs(vals[i] - vals[i - 1]) / dt
                    # 允许 2°C/day，超过此值标记为异常
                    if rate > DataValidator.MAX_DAILY_CHANGE:
                        mask[i] = False
                        stats["rate_violation"] += 1
                        logger.debug(
                            f"时间一致性检查: 点 {i} 变化率 {rate:.2f}°C/day 超过阈值 {DataValidator.MAX_DAILY_CHANGE}°C/day"
                        )

        # 4. 传感器漂移检测（移动窗口偏差，仅 high 灵敏度）
        if sensitivity == "high" and n >= 5:
            window = 5
            for i in range(window, n):
                if not mask[i]:
                    continue

                # 获取窗口内有效值
                window_indices = [j for j in range(max(0, i - window), i) if mask[j]]
                if len(window_indices) >= 3:
                    recent_valid = vals[window_indices]
                    median_recent = np.median(recent_valid)
                    # 如果当前值与近期中位数偏差 > 5°C，可能是漂移
                    if abs(vals[i] - median_recent) > 5.0:
                        mask[i] = False
                        stats["sensor_drift"] += 1
                        logger.debug(
                            f"传感器漂移检测: 点 {i} 偏离近期中位数 {abs(vals[i] - median_recent):.1f}°C > 5°C"
                        )

        return mask, stats

    @staticmethod
    def check_data_sufficiency(n_points: int) -> Tuple[bool, str]:
        """
        P0-2: 硬阈值检查数据充足性

        分层策略：
        - < 3 条：严重不足，无法统计
        - < 7 条：不足，拒绝预测（硬阈值）
        - < 14 条：有限，允许但标记试验性
        - >= 14 条：充足，正常预测

        Args:
            n_points: 数据点数量

        Returns:
            (is_sufficient, message)
                - is_sufficient: 是否允许预测
                - message: 警告信息（空字符串表示无警告）
        """
        if n_points < 3:
            return False, f"数据量严重不足（{n_points} < 3），无法进行任何统计预测"
        elif n_points < 7:
            return (
                False,
                f"数据量不足（{n_points} < 7），未达到时序预测最低要求，"
                f"建议至少采集 7 个检测点后再尝试预测",
            )
        elif n_points < 14:
            return (
                True,
                f"数据量有限（{n_points} < 14），预测结果不确定性较高，"
                f"建议结合现场巡检综合判断",
            )
        else:
            return True, ""
