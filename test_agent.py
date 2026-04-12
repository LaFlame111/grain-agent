"""
Agent 功能测试脚本

测试不同查询意图下的工具选择和调用
"""

import httpx
# Monkeypatch httpx.Client.__init__ to ignore 'app' argument
original_init = httpx.Client.__init__

def new_init(self, *args, **kwargs):
    if 'app' in kwargs:
        kwargs.pop('app')
    original_init(self, *args, **kwargs)

httpx.Client.__init__ = new_init

from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)


def print_separator(char="=", length=80):
    print(char * length)


def test_agent_query(query: str, description: str = ""):
    """测试单个查询"""
    
    print_separator()
    if description:
        print(f"📝 测试: {description}")
    print(f"💬 用户查询: {query}")
    print_separator()
    print()
    
    # 发送请求
    response = client.post("/api/v1/agent/chat", json={"query": query})
    
    if response.status_code == 200:
        result = response.json()
        
        print(f"🎯 识别意图: {result['intent']}")
        print()
        
        print(f"🔧 调用工具:")
        for i, tool_call in enumerate(result['tool_calls'], 1):
            print(f"  {i}. {tool_call['tool']}")
            if tool_call.get('params'):
                print(f"     参数: {tool_call['params']}")
        print()
        
        print(f"💡 Agent 回答:")
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


def main():
    """主测试函数"""
    
    print()
    print_separator("=")
    print("🤖 粮情分析 Agent - 功能测试 (V008)")
    print_separator("=")
    print()
    print("测试 Agent 在不同查询意图下的工具选择和调用能力")
    print()
    
    # 测试用例
    test_cases = [
        {
            "query": "请查询Q1仓在2026年1月4日到5日的粮温情况并给出储藏建议。",
            "description": "单仓查询 - 应调用 T2→T3→T6"
        },
        {
            "query": "对比P1仓和Q1仓在2026年1月4日到5日的粮温，哪个更高？",
            "description": "仓间对比 - 应调用 T5→T6"
        },
        {
            "query": "比较Q1仓在2026年1月4日与1月5日的粮温趋势是否升高。",
            "description": "时间对比 - 应调用 T4→T6"
        },
        {
            "query": "请巡检Q1仓在2026年1月4日到5日的粮温情况。",
            "description": "全库巡检 - 应调用 T1→T6"
        }
    ]
    
    success_count = 0
    total_count = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试 {i}/{total_count}")
        print(f"{'='*80}\n")
        
        if test_agent_query(test_case["query"], test_case["description"]):
            success_count += 1
        
        print()
    
    # 总结
    print_separator("=")
    print(f"✅ 测试完成: {success_count}/{total_count} 通过")
    print_separator("=")
    print()
    
    # 测试查询示例接口
    print("📚 获取查询示例...")
    response = client.get("/api/v1/agent/examples")
    if response.status_code == 200:
        examples = response.json()
        print(f"✓ 共有 {len(examples['examples'])} 种查询类型")
        for example in examples['examples']:
            print(f"  - {example['description']}: {len(example['queries'])} 个示例")
    print()
    
    # 测试对话历史
    print("📜 获取对话历史...")
    response = client.get("/api/v1/agent/history")
    if response.status_code == 200:
        history = response.json()
        print(f"✓ 共有 {history['total']} 条对话记录")
    print()
    
    if success_count == total_count:
        print("🎉 所有测试通过！Agent 工作正常！")
    else:
        print(f"⚠️ 部分测试失败，请检查错误信息")


if __name__ == "__main__":
    main()

