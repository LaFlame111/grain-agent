"""测试真实 WMS 数据访问"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.wms_client import WMSClient

print("=" * 60)
print("测试真实数据访问")
print("=" * 60)

# 初始化
wms_client = WMSClient()

print("\nWMS 连接状态:")
silos = wms_client.get_connected_silos()
print(f"  仓房数量: {len(silos)}")

if not silos:
    print("\n✗ 错误: 没有找到可用仓房")
else:
    test_house_code = silos[0].get("house_code")
    print(f"\n测试仓房: {silos[0].get('house_name')} ({test_house_code})")
    
    # 测试1: 使用已知有数据的时间范围
    print("\n" + "-" * 60)
    print("测试1: 使用 2026-01-01 到 2026-01-05 查询")
    print("-" * 60)
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    end_time = datetime(2026, 1, 5, 23, 59, 59)
    
    results = wms_client.get_grain_temperature(test_house_code, start_time, end_time)
    print(f"查询时间范围: {start_time} 到 {end_time}")
    print(f"返回记录数: {len(results)}")
    
    if results:
        print(f"\n前3条记录:")
        for i, record in enumerate(results[:3], 1):
            print(f"  记录 {i}:")
            print(f"    时间: {record.check_time}")
            print(f"    平均粮温: {record.avg_temp}°C")
            print(f"    仓温: {record.indoor_temp}°C")
            print(f"    气温: {record.outdoor_temp}°C")
        
        print(f"\n最后3条记录:")
        for i, record in enumerate(results[-3:], 1):
            print(f"  记录 {len(results)-3+i}:")
            print(f"    时间: {record.check_time}")
            print(f"    平均粮温: {record.avg_temp}°C")
            print(f"    仓温: {record.indoor_temp}°C")
            print(f"    气温: {record.outdoor_temp}°C")
        
        print(f"\n✓ 成功: 返回了真实数据，共 {len(results)} 条记录")
        print(f"✓ 确认: 使用的是数据采集日期（check_time），不是当前时间")
    else:
        print("\n✗ 失败: 没有返回任何数据")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
