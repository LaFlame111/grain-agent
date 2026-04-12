#!/bin/bash
# Grain Agent V008 - 优雅停止脚本
# 功能：优雅地停止服务，先尝试 SIGTERM，失败后再强制终止

# 默认参数
PORT=${1:-8000}

# 设置错误处理
set -e

# 颜色定义
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}Grain Agent V008 - 服务停止脚本${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/.server.pid"

# 1. 从 PID 文件读取进程 ID
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" | tr -d '[:space:]')
    echo -e "${YELLOW}[1/3] 从 PID 文件读取进程 ID: ${PID}${NC}"
    
    if ps -p $PID > /dev/null 2>&1; then
        PROC_NAME=$(ps -p $PID -o comm= 2>/dev/null || echo "unknown")
        echo -e "${YELLOW}  发现进程: ${PROC_NAME} (PID: ${PID})${NC}"
        echo -e "${YELLOW}  正在优雅停止...${NC}"
        
        # 尝试优雅停止（发送 SIGTERM）
        if kill -TERM $PID 2>/dev/null; then
            # 等待进程结束（最多等待 5 秒）
            for i in {1..5}; do
                sleep 1
                if ! ps -p $PID > /dev/null 2>&1; then
                    echo -e "${GREEN}  ✅ 进程已优雅停止${NC}"
                    break
                fi
            done
            
            # 检查进程是否还在运行
            if ps -p $PID > /dev/null 2>&1; then
                echo -e "${YELLOW}  ⚠️  进程仍在运行，强制终止...${NC}"
                kill -9 $PID 2>/dev/null || true
                echo -e "${GREEN}  ✅ 进程已强制终止${NC}"
            fi
        else
            echo -e "${YELLOW}  ⚠️  停止失败，尝试强制终止...${NC}"
            kill -9 $PID 2>/dev/null || true
        fi
        
        # 清理 PID 文件
        rm -f "$PID_FILE"
    else
        echo -e "${YELLOW}  ⚠️  PID 文件中的进程不存在，清理 PID 文件${NC}"
        rm -f "$PID_FILE"
    fi
fi

# 2. 检查端口占用
echo -e "${YELLOW}[2/3] 检查端口 ${PORT} 占用...${NC}"
PORT_PIDS=$(lsof -ti:${PORT} 2>/dev/null || true)

if [ -n "$PORT_PIDS" ]; then
    for pid in $PORT_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            PROC_NAME=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
            # 检查是否是 python 进程
            if echo "$PROC_NAME" | grep -qi "python"; then
                echo -e "${YELLOW}  发现占用端口的进程: ${PROC_NAME} (PID: ${pid})${NC}"
                echo -e "${YELLOW}  正在停止...${NC}"
                kill -9 $pid 2>/dev/null || true
                echo -e "${GREEN}  ✅ 进程已停止${NC}"
            fi
        fi
    done
else
    echo -e "${GREEN}  ✅ 端口 ${PORT} 未被占用${NC}"
fi

# 3. 清理 uvicorn 进程
echo -e "${YELLOW}[3/3] 清理 uvicorn 进程...${NC}"
UVICORN_PIDS=$(pgrep -f "uvicorn" 2>/dev/null || true)

if [ -n "$UVICORN_PIDS" ]; then
    for pid in $UVICORN_PIDS; do
        echo -e "${YELLOW}  终止进程: uvicorn (PID: ${pid})${NC}"
        kill -9 $pid 2>/dev/null || true
    done
    echo -e "${GREEN}  ✅ uvicorn 进程已清理${NC}"
else
    echo -e "${GREEN}  ✅ 无 uvicorn 进程运行${NC}"
fi

echo ""
echo -e "${CYAN}============================================================${NC}"
echo -e "${GREEN}✅ 服务已停止${NC}"
echo -e "${CYAN}============================================================${NC}"
