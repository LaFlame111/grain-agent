"""
V008 路由检查脚本

检查 FastAPI 应用的路由配置。
"""
import sys
import os

# Add current directory to sys.path
sys.path.append(os.getcwd())

try:
    from app.main import app
    print("Successfully imported app (V008)")
    
    print("\nRoutes:")
    for route in app.routes:
        if hasattr(route, "path"):
            methods = ", ".join(route.methods) if hasattr(route, "methods") else "N/A"
            print(f"- {route.path} [{methods}]")
            
except Exception as e:
    print(f"Error importing app: {e}")
    import traceback
    traceback.print_exc()
