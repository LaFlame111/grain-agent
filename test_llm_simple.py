"""最简单的 LLM 调用测试"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 设置输出编码为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 加载 .env 文件
env_path = Path(__file__).parent / ".env"
print(f"加载 .env 文件: {env_path}")
print(f"文件是否存在: {env_path.exists()}")
load_dotenv(env_path)

api_key = os.getenv("DASHSCOPE_API_KEY", "")
print(f"API Key 长度: {len(api_key)}")
print(f"API Key 前10位: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else api_key}")

if not api_key:
    print("[ERROR] DASHSCOPE_API_KEY 未设置!")
    exit(1)

# 调用 LLM
from openai import OpenAI

print(f"\n初始化 OpenAI 客户端...")
print(f"Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1")
print(f"Model: qwen-max")

client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

print("\n正在调用 qwen-max...")
try:
    response = client.chat.completions.create(
        model="qwen-max",
        messages=[{"role": "user", "content": "你好，请用一句话介绍自己"}],
        temperature=0.3,
        timeout=30.0
    )
    print("[SUCCESS] 调用成功!")
    print(f"回答: {response.choices[0].message.content}")
except Exception as e:
    print(f"[ERROR] 调用失败!")
    print(f"错误类型: {type(e).__name__}")
    print(f"错误信息: {str(e)}")
    import traceback
    traceback.print_exc()

