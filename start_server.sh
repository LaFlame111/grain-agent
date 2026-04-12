#!/bin/bash
# Grain Agent V008 - 智能启动脚本
# 功能：启动前自动清理残留进程，启动后记录 PID，支持优雅关闭

# 默认参数
PORT=${1:-8000}
HOST=${2:-"0.0.0.0"}
DEBUG=${3:-"false"}

# 设置错误处理
set -e

# 设置编码
export PYTHONIOENCODING="utf-8"

# 颜色定义
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}Grain Agent V008 - 服务启动脚本${NC}"
echo -e "${CYAN}============================================================${NC}"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="${SCRIPT_DIR}/.server.pid"
LOG_FILE="${SCRIPT_DIR}/server.log"

# 1. 检查并清理残留进程
echo -e "${YELLOW}[1/4] 检查端口占用...${NC}"
PORT_PIDS=$(lsof -ti:${PORT} 2>/dev/null || true)

if [ -n "$PORT_PIDS" ]; then
    echo -e "${YELLOW}  发现端口 ${PORT} 被占用，正在清理...${NC}"
    for pid in $PORT_PIDS; do
        if ps -p $pid > /dev/null 2>&1; then
            proc_name=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
            echo -e "${YELLOW}  终止进程: ${proc_name} (PID: ${pid})${NC}"
            kill -9 $pid 2>/dev/null || true
        fi
    done
    sleep 1
fi

# 2. 清理 uvicorn 进程
echo -e "${YELLOW}[2/4] 清理 uvicorn 进程...${NC}"
UVICORN_PIDS=$(pgrep -f "uvicorn" 2>/dev/null || true)

if [ -n "$UVICORN_PIDS" ]; then
    for pid in $UVICORN_PIDS; do
        echo -e "${YELLOW}  终止进程: uvicorn (PID: ${pid})${NC}"
        kill -9 $pid 2>/dev/null || true
    done
else
    echo -e "${GREEN}  ✅ 无 uvicorn 进程运行${NC}"
fi

# 3. 检查环境变量
echo -e "${YELLOW}[3/4] 检查环境配置...${NC}"
if [ -z "$DASHSCOPE_API_KEY" ]; then
    echo -e "${RED}  ⚠️  警告: DASHSCOPE_API_KEY 未设置!${NC}"
    echo -e "${RED}  请设置环境变量或创建 .env 文件${NC}"
fi

# 4. 启动服务
echo -e "${YELLOW}[4/4] 启动服务...${NC}"
echo -e "${GREEN}  端口: ${PORT}${NC}"
echo -e "${GREEN}  主机: ${HOST}${NC}"
echo -e "${GREEN}  调试模式: ${DEBUG}${NC}"
echo ""

# 设置调试环境变量
if [ "$DEBUG" = "true" ]; then
    export DEBUG="true"
    export EXPOSE_DOCS="true"
fi

# 启动 uvicorn
echo -e "${GREEN}正在启动服务...${NC}"
echo -e "${CYAN}按 Ctrl+C 优雅停止服务${NC}"
echo ""

# 清理旧的 PID 文件
[ -f "$PID_FILE" ] && rm -f "$PID_FILE"

# 启动服务并记录 PID
python -m uvicorn app.main:app --host "$HOST" --port "$PORT" --reload > "$LOG_FILE" 2>&1 &
SERVER_PID=$!

# 保存 PID
echo $SERVER_PID > "$PID_FILE"
echo -e "${GREEN}✅ 服务已启动 (PID: ${SERVER_PID})${NC}"
echo -e "${CYAN}📝 日志文件: ${LOG_FILE}${NC}"
echo -e "${CYAN}🆔 PID 文件: ${PID_FILE}${NC}"
echo ""
echo -e "${GREEN}服务地址: http://${HOST}:${PORT}${NC}"
if [ "$DEBUG" = "true" ]; then
    echo -e "${GREEN}API 文档: http://localhost:${PORT}/docs${NC}"
fi
echo ""

# 等待进程结束
trap "echo ''; echo -e '${YELLOW}服务已停止${NC}'; [ -f '$PID_FILE' ] && rm -f '$PID_FILE'; exit 0" INT TERM

wait $SERVER_PID

# 清理 PID 文件
[ -f "$PID_FILE" ] && rm -f "$PID_FILE"
echo ""
echo -e "${YELLOW}服务已停止${NC}"
