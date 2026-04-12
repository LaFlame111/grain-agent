import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.agent_service import AgentService

def test_agent_v008_flow():
    print("= " * 60)
    print("V008 Agent 端到端集成测试")
    print("=" * 60)
    
    agent = AgentService()
    
    # 测试问题 0: 查询连接的仓房列表
    query0 = "我想了解连接的仓房列表。"
    print(f"\n[Q0] 用户: {query0}")
    resp0 = agent.chat(query0)
    print(f"Agent 回答: {resp0.get('answer')}")
    print(f"调用的工具: {[t['tool'] for t in resp0.get('tool_calls', [])]}")

    # 测试问题 1: 查询真实仓房信息
    query1 = "我想了解 Q1 仓的基本情况。"
    print(f"\n[Q1] 用户: {query1}")
    resp1 = agent.chat(query1)
    print(f"Agent 回答: {resp1.get('answer')}")
    print(f"调用的工具: {[t['tool'] for t in resp1.get('tool_calls', [])]}")

    # 测试问题 2: 预测粮温趋势 (使用 Q1 仓，因为它有 2 条数据，满足预测最低要求)
    query2 = "根据 2026年1月1日到5日 的数据，预测 Q1 仓接下来的粮温变化趋势。"
    print(f"\n[Q2] 用户: {query2}")
    resp2 = agent.chat(query2)
    print(f"Agent 回答: {resp2.get('answer')}")
    print(f"调用的工具及参数: {resp2.get('tool_calls')}")
    
    # 测试问题 3: 生成三温图 (同样使用 Q1)
    query3 = "请为 Q1 仓生成一份 2026年1月1日到5日 的三温图。"
    print(f"\n[Q3] 用户: {query3}")
    resp3 = agent.chat(query3)
    print(f"Agent 回答: {resp3.get('answer')}")

    print("\n" + "=" * 60)
    print("Agent 测试完成")
    print("=" * 60)

if __name__ == "__main__":
    test_agent_v008_flow()
