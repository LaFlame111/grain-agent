#!/usr/bin/env bash
# Grain Agent — 启动脚本（Git Bash / WSL）
# 用法: bash start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
PORT=8000

echo "=============================="
echo " Grain Agent 启动"
echo "=============================="

# 1. 如果已有 pid 文件，先尝试停止旧进程
if [ -f "$PID_FILE" ]; then
    OLD_PIDS=$(cat "$PID_FILE")
    echo "[1/3] 发现旧 PID 文件，停止旧进程: $OLD_PIDS"
    for pid in $OLD_PIDS; do
        powershell.exe -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
    done
    rm -f "$PID_FILE"
    sleep 1
fi

# 2. 兜底：强制清理端口
LISTENING=$(powershell.exe -NoProfile -Command "
(Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue).OwningProcess" 2>/dev/null | tr -d '\r')
if [ -n "$LISTENING" ]; then
    echo "[1/3] 端口 $PORT 仍被 PID $LISTENING 占用，强制清理..."
    for pid in $LISTENING; do
        # 同时杀掉该进程及其父进程（处理 nohup 层）
        PARENT=$(powershell.exe -NoProfile -Command "
(Get-CimInstance Win32_Process -Filter 'ProcessId=$pid' -ErrorAction SilentlyContinue).ParentProcessId" 2>/dev/null | tr -d '\r')
        powershell.exe -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
        if [ -n "$PARENT" ] && [ "$PARENT" != "0" ]; then
            powershell.exe -NoProfile -Command "Stop-Process -Id $PARENT -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
        fi
    done
    sleep 1
fi

# 3. 启动服务器
echo "[2/3] 启动 uvicorn..."
cd "$SCRIPT_DIR"
nohup python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    >> server.log 2>> server_error.log &

NOHUP_PID=$!
sleep 2

# 找 python 子进程 PID
PYTHON_PID=$(powershell.exe -NoProfile -Command "
(Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue).OwningProcess" 2>/dev/null | tr -d '\r' | head -1)

# 把两个 PID 都存起来，确保 stop 时能全部清理
echo "$NOHUP_PID $PYTHON_PID" > "$PID_FILE"
echo "[3/3] 已启动"
echo "  nohup PID : $NOHUP_PID"
echo "  python PID: $PYTHON_PID"
echo "  PID 文件  : $PID_FILE"
echo ""
echo "前端地址: http://127.0.0.1:$PORT/ui"
echo "健康检查: http://127.0.0.1:$PORT/"
echo ""
echo "停止服务器请运行: bash stop.sh"
