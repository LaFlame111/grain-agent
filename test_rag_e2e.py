"""RAG 端到端测试：通过 API 发送请求，验证 LLM 是否调用 knowledge_search"""
import httpx
import json

BASE_URL = "http://localhost:8000/api/v1/agent/chat"

queries = [
    "小麦储存的安全温度标准是多少？",
    "什么条件下应该启动机械通风？",
    "1号仓当前温度是多少？",
]

for q in queries:
    print(f"{'='*60}")
    print(f"问题: {q}")
    print(f"{'='*60}")

    try:
        r = httpx.post(BASE_URL, json={"query": q}, timeout=60)
        data = r.json()

        tools = [t["tool"] for t in data.get("tool_calls", [])]
        has_rag = "knowledge_search" in tools
        print(f"触发工具: {tools}")
        print(f"是否调用 knowledge_search: {'是' if has_rag else '否'}")
        print(f"回答: {data.get('answer', '')[:200]}")
    except Exception as e:
        print(f"请求失败: {e}")

    print()
