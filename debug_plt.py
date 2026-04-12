import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.join(os.getcwd(), "V008"))

from app.services.tools import GrainTools

def check_plt():
    tools = GrainTools()
    print(f"plt defined in GrainTools: {'plt' in globals() or 'plt' in dir(sys.modules['app.services.tools'])}")
    import app.services.tools
    print(f"plt in app.services.tools: {hasattr(app.services.tools, 'plt')}")

if __name__ == "__main__":
    check_plt()
