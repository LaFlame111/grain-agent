"""
V008 版本交互式 API 测试脚本

支持通过键盘输入时间区间进行查询，例如：
- 单月查询: "2026年1月"
- 月份范围: "2026年1月-2026年12月"
- 年度查询: "2026年"
"""
import requests
import json
import sys
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple

# 添加项目路径以导入 WMS 客户端
sys.path.insert(0, str(Path(__file__).parent))

from app.services.wms_client import WMSClient

url = "http://127.0.0.1:8000/api/v1/agent/chat"
headers = {"Content-Type": "application/json"}

def check_server():
    """检查服务器是否运行"""
    try:
        response = requests.get("http://127.0.0.1:8000/docs", timeout=2)
        return True
    except requests.exceptions.ConnectionError:
        return False

def get_available_house_codes():
    """获取可用的仓号列表（真实 WMS）"""
    client = WMSClient()
    try:
        silos = client.get_connected_silos()
        if not silos:
            return []
        # 优先使用短名（更贴近日常提问）
        return [s.get("short_name") or s.get("house_code") for s in silos]
    except Exception as e:
        print(f"[WARN] 无法获取 WMS 仓房列表: {e}")
        return []

def get_data_time_range():
    """获取推荐的查询时间范围（真实 WMS）"""
    # 真实 WMS 已知存在数据的时间区间
    return (datetime(2026, 1, 1, 0, 0, 0), datetime(2026, 1, 5, 23, 59, 59))

def parse_time_input(time_str: str) -> Optional[Tuple[datetime, datetime]]:
    """
    解析用户输入的时间字符串
    
    支持的格式：
    - "2026年1月" -> 2026-01-01 00:00:00 到 2026-01-31 23:59:59
    - "2026年1月-2026年12月" -> 2026-01-01 00:00:00 到 2026-12-31 23:59:59
    - "2026年" -> 2026-01-01 00:00:00 到 2026-12-31 23:59:59
    
    Returns:
        (start_time, end_time) 元组，如果解析失败返回 None
    """
    time_str = time_str.strip()
    
    # 格式1: "2026年1月"
    pattern1 = r'(\d{4})年(\d{1,2})月'
    match1 = re.match(pattern1, time_str)
    if match1:
        year = int(match1.group(1))
        month = int(match1.group(2))
        start_time = datetime(year, month, 1)
        # 计算该月的最后一天
        if month == 12:
            end_time = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_time = datetime(year, month + 1, 1) - timedelta(seconds=1)
        return (start_time, end_time)
    
    # 格式2: "2026年1月-2026年12月"
    pattern2 = r'(\d{4})年(\d{1,2})月-(\d{4})年(\d{1,2})月'
    match2 = re.match(pattern2, time_str)
    if match2:
        start_year = int(match2.group(1))
        start_month = int(match2.group(2))
        end_year = int(match2.group(3))
        end_month = int(match2.group(4))
        
        start_time = datetime(start_year, start_month, 1)
        # 计算结束月份的最后一天
        if end_month == 12:
            end_time = datetime(end_year + 1, 1, 1) - timedelta(seconds=1)
        else:
            end_time = datetime(end_year, end_month + 1, 1) - timedelta(seconds=1)
        return (start_time, end_time)
    
    # 格式3: "2026年"
    pattern3 = r'(\d{4})年$'
    match3 = re.match(pattern3, time_str)
    if match3:
        year = int(match3.group(1))
        start_time = datetime(year, 1, 1)
        end_time = datetime(year + 1, 1, 1) - timedelta(seconds=1)
        return (start_time, end_time)
    
    return None

def build_query(house_code: str, time_range: Optional[Tuple[datetime, datetime]], query_type: str) -> str:
    """
    根据时间范围和查询类型构建查询语句
    
    Args:
        house_code: 仓号
        time_range: 时间范围 (start_time, end_time)
        query_type: 查询类型 ("daily", "trend", "chart", "inspection")
    
    Returns:
        查询语句字符串
    """
    house_name = f"{house_code}号仓"
    
    if time_range:
        start_time, end_time = time_range
        start_str = start_time.strftime("%Y年%m月%d日")
        end_str = end_time.strftime("%Y年%m月%d日")
        
        if query_type == "daily":
            # 日报查询
            if start_time.year == end_time.year and start_time.month == end_time.month:
                # 单月查询
                month_str = start_time.strftime("%Y年%m月")
                return f"生成{house_name}在{month_str}的日报"
            else:
                # 月份范围查询
                return f"生成{house_name}从{start_str}到{end_str}的日报"
        
        elif query_type == "trend":
            # 趋势分析查询
            if start_time.year == end_time.year and start_time.month == end_time.month:
                month_str = start_time.strftime("%Y年%m月")
                return f"分析{house_name}在{month_str}的粮温变化趋势"
            else:
                return f"分析{house_name}从{start_str}到{end_str}的粮温变化趋势"
        
        elif query_type == "chart":
            # 图表生成查询
            if start_time.year == end_time.year and start_time.month == end_time.month:
                month_str = start_time.strftime("%Y年%m月")
                return f"给我生成{house_name}在{month_str}的三温图和两湿图"
            else:
                return f"给我生成{house_name}从{start_str}到{end_str}的三温图和两湿图"
        
        elif query_type == "inspection":
            # 巡检查询
            if start_time.year == end_time.year and start_time.month == end_time.month:
                month_str = start_time.strftime("%Y年%m月")
                return f"巡检{house_name}在{month_str}的粮温情况"
            else:
                return f"巡检{house_name}从{start_str}到{end_str}的粮温情况"
    
    # 如果没有时间范围，使用默认查询
    if query_type == "daily":
        return f"生成{house_name}的日报"
    elif query_type == "trend":
        return f"分析{house_name}的粮温变化趋势"
    elif query_type == "chart":
        return f"给我生成{house_name}的三温图和两湿图"
    elif query_type == "inspection":
        return f"巡检{house_name}的粮温情况"
    
    return f"{house_name}的粮温情况如何？"

def send_query(query: str) -> bool:
    """
    发送查询请求并显示结果
    
    Returns:
        是否成功
    """
    try:
        print(f"\n正在发送查询: {query}")
        print("-" * 60)
        
        response = requests.post(
            url, 
            json={"query": query}, 
            headers=headers, 
            timeout=120  # 报告生成可能需要更长时间
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 请求成功")
            print(f"意图: {result.get('intent', 'N/A')}")
            
            tool_calls = result.get('tool_calls', [])
            if tool_calls:
                tools = [tc.get('tool', 'N/A') for tc in tool_calls]
                print(f"工具调用: {', '.join(tools)}")
            else:
                print("工具调用: 无")
            
            answer = result.get('answer', '')
            if answer:
                print(f"\n回答:")
                print("-" * 60)
                # 完整显示回答
                print(answer)
                print("-" * 60)
            else:
                print("回答: 无")
            
            return True
        else:
            print(f"❌ 错误: HTTP {response.status_code}")
            print(f"响应: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误: 无法连接到服务器")
        print("请确保服务器正在运行")
        return False
    except requests.exceptions.Timeout:
        print("❌ 超时错误: 请求超时（>120秒）")
        return False
    except Exception as e:
        print(f"❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("V008 版本交互式 API 测试")
    print("=" * 60)
    
    # 检查服务器
    if not check_server():
        print("\n❌ 错误: 服务器未运行！")
        print("请先启动服务器:")
        print("  cd V008")
        print("  .\\start_server.ps1")
        sys.exit(1)
    
    print("[OK] 服务器运行中\n")
    
    # 获取可用仓号
    house_codes = get_available_house_codes()
    print(f"[INFO] 可用仓号: {', '.join(house_codes)}")
    
    # 获取数据时间范围
    data_time_range = get_data_time_range()
    if data_time_range:
        print(f"[INFO] 数据时间范围: {data_time_range[0].strftime('%Y-%m-%d')} 到 {data_time_range[1].strftime('%Y-%m-%d')}")
    print()
    
    # 选择仓号
    if len(house_codes) > 1:
        print("请选择仓号:")
        for i, code in enumerate(house_codes, 1):
            print(f"  {i}. {code}号仓")
        try:
            choice = int(input("\n请输入序号 (直接回车使用第一个): ").strip() or "1")
            if 1 <= choice <= len(house_codes):
                selected_house_code = house_codes[choice - 1]
            else:
                selected_house_code = house_codes[0]
                print(f"[INFO] 使用默认仓号: {selected_house_code}")
        except ValueError:
            selected_house_code = house_codes[0]
            print(f"[INFO] 使用默认仓号: {selected_house_code}")
    else:
        selected_house_code = house_codes[0]
        print(f"[INFO] 使用仓号: {selected_house_code}")
    
    print("\n" + "=" * 60)
    print("查询类型说明:")
    print("=" * 60)
    print("1. 日报查询 (daily) - 生成指定时间段的日报")
    print("2. 趋势分析 (trend) - 分析指定时间段的粮温变化趋势")
    print("3. 图表生成 (chart) - 生成三温图和两湿图")
    print("4. 巡检查询 (inspection) - 巡检指定时间段的粮温情况")
    print("5. 自定义查询 (custom) - 直接输入查询语句")
    print("=" * 60)
    
    # 交互式查询循环
    while True:
        print("\n" + "=" * 60)
        print("请选择查询类型:")
        print("  1. 日报查询")
        print("  2. 趋势分析")
        print("  3. 图表生成")
        print("  4. 巡检查询")
        print("  5. 自定义查询")
        print("  0. 退出")
        print("=" * 60)
        
        query_type_choice = input("请输入选项 (0-5): ").strip()
        
        if query_type_choice == "0":
            print("\n退出程序")
            break
        
        query_type = None
        if query_type_choice == "1":
            query_type = "daily"
        elif query_type_choice == "2":
            query_type = "trend"
        elif query_type_choice == "3":
            query_type = "chart"
        elif query_type_choice == "4":
            query_type = "inspection"
        elif query_type_choice == "5":
            query_type = "custom"
        else:
            print("❌ 无效选项，请重新选择")
            continue
        
        # 输入时间范围
        time_range = None
        if query_type != "custom":
            print("\n请输入时间范围:")
            print("  格式示例:")
            print("    - 单月: 2026年1月")
            print("    - 月份范围: 2026年1月-2026年12月")
            print("    - 年度: 2026年")
            print("    - 直接回车跳过时间范围")
            
            time_input = input("\n时间范围: ").strip()
            
            if time_input:
                time_range = parse_time_input(time_input)
                if time_range:
                    start_time, end_time = time_range
                    print(f"✓ 解析成功: {start_time.strftime('%Y-%m-%d')} 到 {end_time.strftime('%Y-%m-%d')}")
                else:
                    print("❌ 时间格式解析失败，请检查格式")
                    print("  支持的格式: '2026年1月', '2026年1月-2026年12月', '2026年'")
                    continue
            else:
                print("[INFO] 未指定时间范围，将查询所有可用数据")
        
        # 构建查询语句
        if query_type == "custom":
            query = input("\n请输入查询语句: ").strip()
            if not query:
                print("❌ 查询语句不能为空")
                continue
        else:
            query = build_query(selected_house_code, time_range, query_type)
        
        # 发送查询
        success = send_query(query)
        
        if success:
            print("\n✓ 查询完成")
        else:
            print("\n✗ 查询失败")
        
        # 询问是否继续
        continue_choice = input("\n是否继续查询? (y/n, 默认y): ").strip().lower()
        if continue_choice == 'n':
            break
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()
