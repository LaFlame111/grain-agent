"""
V008 版本 API 测试脚本

测试 Agent API 接口，使用真实 WMS 数据
"""
import requests
import json
import sys
from pathlib import Path
from datetime import datetime

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

def get_available_silos():
    """获取可用的仓房列表（真实 WMS）"""
    client = WMSClient()
    try:
        silos = client.get_connected_silos()
        return silos if silos else []
    except Exception as e:
        print(f"[WARN] 无法获取 WMS 仓房列表: {e}")
        return []

def main():
    # 检查服务器是否运行
    print("=" * 60)
    print("V008 版本 API 测试")
    print("=" * 60)
    
    if not check_server():
        print("\n❌ 错误: 服务器未运行！")
        print("请先启动服务器:")
        print("  cd V008")
        print("  .\\start_server.ps1")
        sys.exit(1)
    
    print("[OK] 服务器运行中\n")
    
    # 获取可用的仓房
    silos = get_available_silos()
    if not silos:
        print("[ERROR] 未获取到任何 WMS 仓房，无法继续测试")
        sys.exit(1)

    first_silo = silos[0]
    test_short_name = first_silo.get("short_name") or first_silo.get("house_code")
    print(f"[INFO] 可用仓房: {len(silos)} 个，示例: {first_silo.get('house_name')} ({test_short_name})")

    # 使用 WMS 已知有数据的时间范围
    start_str = "2026年1月1日"
    end_str = "2026年1月5日"

    queries = [
        f"{test_short_name}仓在{start_str}到{end_str}的粮温情况如何？",
        f"查询{test_short_name}仓在{start_str}到{end_str}之间的数据",
        f"给我生成{test_short_name}仓在{start_str}到{end_str}的三温图",
        f"生成{test_short_name}仓在{start_str}到{end_str}的日报"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*60}")
        print(f"测试 {i}/{len(queries)}: {query}")
        print('='*60)
        
        try:
            response = requests.post(
                url, 
                json={"query": query}, 
                headers=headers, 
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 请求成功")
                print(f"意图: {result.get('intent', 'N/A')}")
                
                tool_calls = result.get('tool_calls', [])
                if tool_calls:
                    tools = [tc.get('tool', 'N/A') for tc in tool_calls]
                    print(f"工具调用: {tools}")
                else:
                    print("工具调用: 无")
                
                answer = result.get('answer', '')
                if answer:
                    # 限制输出长度
                    if len(answer) > 500:
                        print(f"回答: {answer[:500]}...")
                    else:
                        print(f"回答: {answer}")
                else:
                    print("回答: 无")
            else:
                print(f"❌ 错误: HTTP {response.status_code}")
                print(f"响应: {response.text[:200]}")
                
        except requests.exceptions.ConnectionError:
            print("❌ 连接错误: 无法连接到服务器")
            print("请确保服务器正在运行")
            break
        except requests.exceptions.Timeout:
            print("❌ 超时错误: 请求超时（>60秒）")
        except Exception as e:
            print(f"❌ 异常: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()