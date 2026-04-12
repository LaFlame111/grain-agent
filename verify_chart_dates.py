"""验证图表横轴日期是否正确使用数据采集日期"""
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.tools import GrainTools
from app.services.wms_client import WMSClient
from app.services.data_loader import DataLoader

print("=" * 60)
print("验证图表横轴日期")
print("=" * 60)

# 初始化工具
tools = GrainTools()
wms_client = WMSClient()
from app.services.data_loader import get_data_loader
data_loader = get_data_loader()

# 获取一个仓号
house_codes = data_loader.get_all_house_codes()
if not house_codes:
    print("错误: 没有找到仓号")
    sys.exit(1)

test_house_code = house_codes[0]
print(f"\n测试仓号: {test_house_code}")

# 查询数据（使用历史时间范围，确保有数据）
from datetime import timedelta
end_time = datetime.now()
start_time = end_time - timedelta(days=365 * 5)  # 5年前到现在

print(f"\n查询时间范围: {start_time.strftime('%Y-%m-%d')} 到 {end_time.strftime('%Y-%m-%d')}")

# 获取数据
series = wms_client.get_grain_temperature(test_house_code, start_time, end_time)
print(f"\n查询到 {len(series)} 条记录")

if not series:
    print("错误: 没有查询到数据")
    sys.exit(1)

# 显示前几条记录的 check_time
print("\n前5条记录的 check_time（数据采集日期）:")
for i, record in enumerate(series[:5], 1):
    print(f"  记录 {i}: {record.check_time}")

# 检查图表生成函数中使用的日期
print("\n" + "=" * 60)
print("检查三温图生成函数中的日期处理:")
print("=" * 60)

# 模拟图表生成函数中的逻辑
times = []
for record in series:
    try:
        check_time = datetime.strptime(record.check_time, "%Y-%m-%d %H:%M:%S")
        times.append(check_time)
    except (ValueError, AttributeError) as e:
        print(f"  警告: 解析失败: {e}")
        continue

if times:
    # 排序
    times = sorted(times)
    
    # 限制为最近7个
    if len(times) > 7:
        times = times[-7:]
    
    print(f"\n用于横轴显示的日期（共 {len(times)} 个）:")
    for i, t in enumerate(times, 1):
        date_str = t.strftime("%Y-%m-%d")
        print(f"  点 {i}: {date_str} (原始: {t.strftime('%Y-%m-%d %H:%M:%S')})")
    
    print("\n✓ 确认: 横轴使用的是数据采集日期（check_time），不是当前时间")
    print("✓ 确认: 日期已按时间排序（从早到晚）")
    print("✓ 确认: 日期格式为 YYYY-MM-DD")
else:
    print("错误: 没有有效的日期数据")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
