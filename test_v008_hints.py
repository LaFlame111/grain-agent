import sys
import os
from datetime import datetime, timedelta

# 确保导入路径正确
sys.path.append(os.path.join(os.getcwd(), "V008"))

from app.services.tools import GrainTools

def test_data_scarcity_hints():
    print("=== 测试 V008 数据稀疏性友好提示规则 ===")
    tools = GrainTools()
    
    # P1 仓在 2026-01-01 到 2026-01-05 期间只有 1 条真实数据
    silo_id = "P1"
    start_time = "2026-01-01 00:00:00"
    end_time = "2026-01-05 23:59:59"
    
    print(f"\n1. 测试三温图熔断 (仓号: {silo_id}, 预期: <= 1 点熔断)")
    result = tools.three_temp_chart(silo_id, start_time=start_time, end_time=end_time)
    print(f"状态: {result.get('status')}")
    print(f"消息: {result.get('message')}")
    
    print(f"\n2. 测试两湿图熔断 (仓号: {silo_id}, 预期: <= 1 点熔断)")
    result = tools.two_humidity_chart(silo_id, start_time=start_time, end_time=end_time)
    print(f"状态: {result.get('status')}")
    print(f"消息: {result.get('message')}")
    
    print(f"\n3. 测试短期预测熔断 (仓号: {silo_id}, 预期: <= 2 点熔断)")
    result = tools.short_term_prediction(silo_id, start_time=start_time, end_time=end_time)
    print(f"状态: {result.get('status')}")
    print(f"消息: {result.get('message')}")
    
    # Q1 仓在 2026-01-01 到 2026-01-05 期间有 2 条真实粮温数据
    silo_id_q1 = "Q1"
    print(f"\n4. 测试 Q1 仓短期预测熔断 (仓号: {silo_id_q1}, 预期: 2 点仍应熔断)")
    result = tools.short_term_prediction(silo_id_q1, start_time=start_time, end_time=end_time)
    print(f"状态: {result.get('status')}")
    print(f"消息: {result.get('message')}")

if __name__ == "__main__":
    test_data_scarcity_hints()
