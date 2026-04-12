import httpx
import json
import time

def test_agent_api():
    # 本地启动的 V008 服务地址
    url = "http://127.0.0.1:8000/api/v1/agent/chat"
    
    # 模拟用户通过 Web 界面提问的序列
    # 我们按顺序提问，以验证 Agent 的对话记忆和编码解析能力
    queries = [
        "我想了解当前连接的仓房列表。",
        "我想了解 Q1 仓的基本情况。",
        "请为 Q1 仓生成一份 2026年1月1日到5日 的三温图。"
    ]
    
    print("=" * 60)
    print("V008 API 接口集成测试 (端到端)")
    print("=" * 60)
    
    # 使用同一个 Client 模拟持续对话（如果有 Session 逻辑，这里会更有用）
    with httpx.Client(timeout=60.0) as client:
        for i, q in enumerate(queries):
            print(f"\n[测试步奏 {i+1}] 用户提问: {q}")
            payload = {"query": q}
            
            try:
                start_time = time.time()
                response = client.post(url, json=payload)
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"Agent 回答: {data.get('answer')}")
                    print(f"意图识别: {data.get('intent')}")
                    
                    # 打印调用的工具细节
                    tool_calls = data.get('tool_calls', [])
                    if tool_calls:
                        print(f"调用的工具: {[t['tool'] for t in tool_calls]}")
                        for t in tool_calls:
                            if 'params' in t:
                                print(f"  -> 参数: {json.dumps(t['params'], ensure_ascii=False)}")
                    
                    print(f"响应耗时: {elapsed:.2f}s")
                else:
                    print(f"API 错误: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"请求失败: {e}")
                print("提示: 请确保您已经运行了 'python -m uvicorn app.main:app' 启动服务。")

    print("\n" + "=" * 60)
    print("API 测试流程结束")
    print("=" * 60)

if __name__ == "__main__":
    test_agent_api()
