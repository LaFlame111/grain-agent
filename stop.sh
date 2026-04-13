#!/usr/bin/env bash
# Grain Agent — 停止脚本（Git Bash / WSL）
# 用法: bash stop.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$SCRIPT_DIR/.server.pid"
PORT=8000

echo "=============================="
echo " Grain Agent 停止"
echo "=============================="

KILLED=0

# 1. 从 pid 文件精确杀进程
if [ -f "$PID_FILE" ]; then
    PIDS=$(cat "$PID_FILE")
    echo "[1/2] 从 PID 文件停止进程: $PIDS"
    for pid in $PIDS; do
        if [ -n "$pid" ] && [ "$pid" != "0" ]; then
            powershell.exe -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
            KILLED=1
        fi
    done
    rm -f "$PID_FILE"
else
    echo "[1/2] 未找到 PID 文件，跳过精确停止"
fi

# 2. 兜底：清理端口上的所有残留进程（含 nohup 父进程）
sleep 1
LISTENING=$(powershell.exe -NoProfile -Command "
(Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue).OwningProcess" 2>/dev/null | tr -d '\r')

if [ -n "$LISTENING" ]; then
    echo "[2/2] 端口 $PORT 仍有残留进程，强制清理..."
    for pid in $LISTENING; do
        PARENT=$(powershell.exe -NoProfile -Command "
(Get-CimInstance Win32_Process -Filter 'ProcessId=$pid' -ErrorAction SilentlyContinue).ParentProcessId" 2>/dev/null | tr -d '\r')
        powershell.exe -NoProfile -Command "Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
        if [ -n "$PARENT" ] && [ "$PARENT" != "0" ]; then
            powershell.exe -NoProfile -Command "Stop-Process -Id $PARENT -Force -ErrorAction SilentlyContinue" 2>/dev/null || true
        fi
        KILLED=1
    done
else
    echo "[2/2] 端口 $PORT 已释放，无需清理"
fi

sleep 1

# 验证
STILL=$(powershell.exe -NoProfile -Command "
(Get-NetTCPConnection -LocalPort $PORT -ErrorAction SilentlyContinue).OwningProcess" 2>/dev/null | tr -d '\r')
if [ -n "$STILL" ]; then
    echo "警告：端口 $PORT 仍被 PID $STILL 占用，请手动处理"
    exit 1
else
    echo "端口 $PORT 已清空"
    [ $KILLED -eq 1 ] && echo "服务器已停止" || echo "服务器本来就没在运行"
fi
