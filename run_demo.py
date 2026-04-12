"""
V003 Agent 自动演示脚本
"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8002"
CHAT_ENDPOINT = f"{BASE_URL}/api/v1/agent/chat"


def print_separator(char="=", length=80):
    print(char * length)


def chat_with_agent(query: str):
    """与 Agent 对话"""
    
    print_separator()
    print(f"💬 用户: {query}")
    print_separator()
    print()
    
    try:
        response = requests.post(CHAT_ENDPOINT, json={"query": query}, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"🎯 识别意图: {result['intent']}")
            print()
            
            print(f"🔧 调用工具: {' → '.join([tc['tool'] for tc in result['tool_calls']])}")
            print()
            
            print(f"🤖 Agent:")
            print("-" * 80)
            print(result['answer'])
            print("-" * 80)
            print()
            
            if result.get('reasoning'):
                print(f"🔬 推理过程:")
                print(result['reasoning'])
                print()
            
            return True
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到服务器")
        return False
    except Exception as e:
        print(f"❌ 发生错误: {str(e)}")
        return False


def main():
    """主函数"""
    
    print()
    print_separator("=")
    print("🤖 粮情分析 Agent - 自动演示 (V003)")
    print_separator("=")
    print()
    
    # 检查服务
    try:
        response = requests.get(BASE_URL, timeout=2)
        if response.status_code == 200:
            info = response.json()
            print(f"✅ {info['message']}")
            print(f"   模式: {info['mode']}")
            print()
        else:
            print("⚠️ 服务响应异常")
            return
    except:
        print("❌ 服务未启动")
        return
    
    # 演示不同类型的查询
    queries = [
        "1号仓的粮温情况如何？",
        "1号仓和2号仓哪个温度更高？",
        "1号仓这周温度比上周高吗？",
        "巡检一下所有粮仓"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*80}")
        print(f"演示 {i}/{len(queries)}")
        print(f"{'='*80}\n")
        
        chat_with_agent(query)
        time.sleep(1)
    
    print_separator("=")
    print("✅ 演示完成！")
    print_separator("=")


if __name__ == "__main__":
    main()
