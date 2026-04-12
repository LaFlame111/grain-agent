"""测试时间范围查询"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from app.services.wms_client import WMSClient
from app.services.tools import GrainTools

print("=" * 60)
print("测试时间范围查询")
print("=" * 60)

tools = GrainTools()
wms_client = WMSClient()

# 获取一个真实仓房
silos = wms_client.get_connected_silos()
if not silos:
    print("[ERROR] 未获取到任何 WMS 仓房，无法继续测试")
    sys.exit(1)

house_code = silos[0].get("house_code")

# 测试查询 2026 年 1 月 1-5 日的数据（真实 WMS 有数据）
start_time = datetime(2026, 1, 1, 0, 0, 0)
end_time = datetime(2026, 1, 5, 23, 59, 59)

print(f"\n查询时间范围: {start_time} 到 {end_time}")

# 查询数据
series = wms_client.get_grain_temperature(house_code, start_time, end_time)
print(f"\n查询到 {len(series)} 条记录")

if series:
    print("\n所有数据点的日期:")
    for i, record in enumerate(series, 1):
        print(f"  {i}. {record.check_time}")
    
    print(f"\n前7个数据点:")
    for i, record in enumerate(series[:7], 1):
        print(f"  {i}. {record.check_time} - 平均粮温: {record.avg_temp}°C")
    
    # 测试图表生成
    print("\n" + "=" * 60)
    print("测试生成三温图（使用指定时间范围）")
    print("=" * 60)
    
    result = tools.generate_three_temp_chart(house_code, start_time=start_time, end_time=end_time)
    print(f"生成结果: {result}")
    
    if result.get("status") == "generated":
        print(f"✓ 图表生成成功: {result.get('file_path')}")
    else:
        print(f"✗ 图表生成失败: {result.get('status')}")
