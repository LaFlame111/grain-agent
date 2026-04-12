"""
V008 兼容数据访问测试脚本

测试本地历史数据加载与真实 WMS 数据访问
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.data_loader import DataLoader
from app.services.wms_client import WMSClient

def test_data_loader():
    """测试本地历史数据加载器（可选）"""
    print("=" * 60)
    print("测试数据加载器")
    print("=" * 60)
    
    loader = DataLoader()
    success = loader.load()
    
    if success:
        print(f"[OK] 数据加载成功，共 {len(loader.raw_data)} 条记录")
        print(f"[OK] 索引建立成功，共 {len(loader.indexed_data)} 个仓号")
        
        # 显示所有仓号
        house_codes = loader.get_all_house_codes()
        print(f"[OK] 可用仓号: {', '.join(house_codes)}")
        
        # 测试查询（使用真实数据的时间范围：2015-2018年）
        if house_codes:
            test_house_code = house_codes[0]
            print(f"\n测试查询仓号: {test_house_code}")
            
            # 真实数据的时间范围：2015-2018年
            start_time = datetime(2015, 1, 1)
            end_time = datetime(2018, 12, 31)
            
            results = loader.query(test_house_code, start_time, end_time)
            print(f"[OK] 查询结果: {len(results)} 条记录（时间范围: 2015-2018）")
            
            if results:
                print(f"\n第一条记录:")
                print(f"  仓房名称: {results[0].house_name}")
                print(f"  检测时间: {results[0].check_time}")
                print(f"  平均粮温: {results[0].avg_temp}°C")
                print(f"  最高粮温: {results[0].max_temp}°C")
                print(f"  最低粮温: {results[0].min_temp}°C")
                print(f"  气温: {results[0].outdoor_temp}°C")
                print(f"  仓温: {results[0].indoor_temp}°C")
                print(f"  气湿: {results[0].outdoor_humidity}%")
                print(f"  仓湿: {results[0].indoor_humidity}%")
    else:
        print("[ERROR] 数据加载失败")
    
    return success

def test_wms_client():
    """测试 WMS 客户端"""
    print("\n" + "=" * 60)
    print("测试 WMS 客户端")
    print("=" * 60)
    
    client = WMSClient()
    
    if client.use_real_data:
        print("[OK] WMSClient 使用真实数据模式")
    else:
        print("[WARN] WMSClient 使用 Mock 数据模式")
    
    # 测试查询粮温数据（使用真实 WMS 数据时间范围）
    silos = client.get_connected_silos()
    if not silos:
        print("[ERROR] 未获取到任何 WMS 仓房")
        return False

    test_house_code = silos[0].get("house_code")
    start_time = datetime(2026, 1, 1)
    end_time = datetime(2026, 1, 5)
    
    print(f"\n测试查询仓号: {test_house_code}")
    print(f"时间范围: {start_time.strftime('%Y-%m-%d')} 到 {end_time.strftime('%Y-%m-%d')}")
    
    results = client.get_grain_temperature(test_house_code, start_time, end_time)
    print(f"[OK] 查询结果: {len(results)} 条记录")
    
    if results:
        print(f"\n前3条记录:")
        for i, record in enumerate(results[:3], 1):
            print(f"  [{i}] {record.check_time}: 平均={record.avg_temp}°C, 气温={record.outdoor_temp}°C, 仓温={record.indoor_temp}°C")
    
    # 测试查询仓房信息
    print(f"\n测试查询仓房信息: {test_house_code}")
    info = client.get_warehouse_info(test_house_code)
    print(f"[OK] 仓房信息:")
    print(f"  仓号: {info.house_code}")
    print(f"  仓房名称: {info.house_name}")
    print(f"  库点名称: {info.depot_name}")
    
    return True

def test_chart_generation():
    """测试图表生成"""
    print("\n" + "=" * 60)
    print("测试图表生成")
    print("=" * 60)
    
    from app.services.tools import GrainTools
    
    tools = GrainTools()
    client = WMSClient()
    silos = client.get_connected_silos()
    if not silos:
        print("[ERROR] 未获取到任何 WMS 仓房")
        return False

    test_house_code = silos[0].get("house_code")
    start_time = datetime(2026, 1, 1)
    end_time = datetime(2026, 1, 5)
    
    # 测试三温图生成（注意：真实数据是2015-2018年的历史数据）
    print(f"\n测试生成三温图（仓号: {test_house_code}）")
    three_temp_result = tools.generate_three_temp_chart(test_house_code, start_time=start_time, end_time=end_time)
    print(f"状态: {three_temp_result.get('status')}")
    if three_temp_result.get('status') == 'generated':
        print(f"[OK] 三温图生成成功: {three_temp_result.get('file_path')}")
    else:
        print(f"[WARN] 三温图生成失败或无数据")
    
    # 测试两湿图生成（注意：真实数据是2015-2018年的历史数据）
    print(f"\n测试生成两湿图（仓号: {test_house_code}）")
    two_humidity_result = tools.generate_two_humidity_chart(test_house_code, start_time=start_time, end_time=end_time)
    print(f"状态: {two_humidity_result.get('status')}")
    if two_humidity_result.get('status') == 'generated':
        print(f"[OK] 两湿图生成成功: {two_humidity_result.get('file_path')}")
    else:
        print(f"[WARN] 两湿图生成失败或无数据")
    
    return True

if __name__ == "__main__":
    print("V008 数据访问功能测试")
    print("=" * 60)
    
    try:
        # 本地历史数据兼容测试（默认跳过）
        if os.getenv("RUN_LOCAL_DATA_TEST") == "1":
            if not test_data_loader():
                print("\n❌ 数据加载器测试失败，退出")
                sys.exit(1)
        else:
            print("[SKIP] 未启用本地历史数据测试（设置 RUN_LOCAL_DATA_TEST=1 可启用）")
        
        # 测试 WMS 客户端
        test_wms_client()
        
        # 测试图表生成
        test_chart_generation()
        
        print("\n" + "=" * 60)
        print("[OK] 所有测试完成")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
