#!/bin/bash
# ============================================================
# 粮情分析智能体 (Grain Agent V008) — 一键部署脚本
#
# 用法：git clone 后，在 V008 目录下执行：
#   bash deploy.sh
#
# 此脚本会自动：
#   1. 从 GitHub Releases 下载 Docker 镜像和数据卷
#   2. 导入 Docker 镜像
#   3. 启动 RAGFlow 容器 + 导入知识库数据
#   4. 安装 Python 依赖
#   5. 引导配置 .env
#
# 前提：已安装 Docker Desktop (29.x+)、Python 3.10+、curl
# ============================================================

set -e

# ── 配置区（发布前修改） ──────────────────────────────
GITHUB_REPO="LaFlame111/grain-agent"
RELEASE_TAG="v1.0.0"                           # ← 替换为实际 release tag
DOWNLOAD_DIR="./ragflow_export"                # 下载目录

# GitHub Releases 中的文件列表
RELEASE_FILES=(
    "images.tar.part-aa"
    "images.tar.part-ab"
    "images.tar.part-ac"
    "vol_mysql.tar.gz"
    "vol_es.tar.gz"
    "vol_minio.tar.gz"
    "vol_redis.tar.gz"
    "docker-compose.yml"
    "docker-compose-base.yml"
    "entrypoint.sh"
    "service_conf.yaml.template"
    "init.sql"
)

# ── 颜色输出 ─────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC}   $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── 前置检查 ─────────────────────────────────────────
echo ""
echo "=========================================="
echo " 粮情分析智能体 V008 — 一键部署"
echo "=========================================="
echo ""

info "检查依赖工具..."

command -v docker >/dev/null 2>&1 || error "未找到 docker，请先安装 Docker Desktop"
command -v python >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || error "未找到 python，请先安装 Python 3.10+"
command -v curl >/dev/null 2>&1 || error "未找到 curl"

# 检查 Docker 是否运行
docker info >/dev/null 2>&1 || error "Docker 未运行，请先启动 Docker Desktop"

success "依赖检查通过"

# ── 第 1 步：下载 Release 文件 ───────────────────────
echo ""
echo "=========================================="
echo " 第 1 步：下载 Docker 镜像和数据卷"
echo "=========================================="

RELEASE_URL="https://github.com/${GITHUB_REPO}/releases/download/${RELEASE_TAG}"

mkdir -p "$DOWNLOAD_DIR"

download_file() {
    local filename="$1"
    local url="${RELEASE_URL}/${filename}"
    local dest="${DOWNLOAD_DIR}/${filename}"

    local max_retries=10
    local attempt=0

    while [ $attempt -lt $max_retries ]; do
        attempt=$((attempt + 1))
        info "下载 ${filename}（第 ${attempt} 次尝试）..."
        if curl -L --progress-bar -C - -o "$dest" "$url"; then
            success "${filename} 下载完成"
            return 0
        else
            local exit_code=$?
            if [ $attempt -lt $max_retries ]; then
                warn "下载中断（exit ${exit_code}），5 秒后断点续传..."
                sleep 5
            else
                error "下载失败（已重试 ${max_retries} 次）：${url}"
            fi
        fi
    done
}

for file in "${RELEASE_FILES[@]}"; do
    download_file "$file"
done

success "所有文件下载完成"

# ── 第 2 步：合并并导入 Docker 镜像 ──────────────────
echo ""
echo "=========================================="
echo " 第 2 步：导入 Docker 镜像（约 4GB，需几分钟）"
echo "=========================================="

IMAGES_TAR="${DOWNLOAD_DIR}/images.tar"

if [ ! -f "$IMAGES_TAR" ]; then
    info "合并分卷文件..."
    cat "${DOWNLOAD_DIR}/images.tar.part-"* > "$IMAGES_TAR"
    success "分卷合并完成"
fi

info "导入镜像（docker load）..."
docker load -i "$IMAGES_TAR"
success "Docker 镜像导入完成"

# 验证
info "验证镜像..."
for img in ragflow mysql elasticsearch minio valkey; do
    if docker images | grep -q "$img"; then
        success "  镜像 ${img} ✓"
    else
        warn "  镜像 ${img} 未找到，可能名称不同"
    fi
done

# ── 第 3 步：部署 RAGFlow 容器 ───────────────────────
echo ""
echo "=========================================="
echo " 第 3 步：启动 RAGFlow 容器"
echo "=========================================="

RAGFLOW_DIR="./ragflow_docker"
mkdir -p "$RAGFLOW_DIR"

# 复制 docker compose 文件
for f in docker-compose.yml docker-compose-base.yml entrypoint.sh service_conf.yaml.template init.sql; do
    if [ -f "${DOWNLOAD_DIR}/${f}" ]; then
        cp "${DOWNLOAD_DIR}/${f}" "${RAGFLOW_DIR}/"
    fi
done

# 确保 entrypoint.sh 可执行
chmod +x "${RAGFLOW_DIR}/entrypoint.sh" 2>/dev/null || true

info "启动 RAGFlow 容器..."
cd "$RAGFLOW_DIR"
docker compose up -d
cd ..

info "等待容器启动（30 秒）..."
sleep 30

# 检查容器状态
if docker compose -f "${RAGFLOW_DIR}/docker-compose.yml" ps | grep -q "Up"; then
    success "RAGFlow 容器已启动"
else
    warn "部分容器可能尚未就绪，继续等待..."
    sleep 30
fi

# ── 第 4 步：导入知识库数据卷 ────────────────────────
echo ""
echo "=========================================="
echo " 第 4 步：导入知识库数据（167 个文档）"
echo "=========================================="

info "停止容器以安全导入数据..."
cd "$RAGFLOW_DIR"
docker compose down
cd ..

# 使用 Windows 格式路径以兼容 Docker Desktop on Windows
EXPORT_ABS="$(cd "$DOWNLOAD_DIR" && pwd -W 2>/dev/null || pwd)"

info "创建数据卷..."
docker volume create docker_mysql_data 2>/dev/null || true
docker volume create docker_esdata01 2>/dev/null || true
docker volume create docker_minio_data 2>/dev/null || true
docker volume create docker_redis_data 2>/dev/null || true

info "导入 MySQL 数据..."
MSYS_NO_PATHCONV=1 docker run --rm -v "docker_mysql_data:/data" -v "${EXPORT_ABS}:/backup:ro" alpine sh -c "cd /data && tar xzf /backup/vol_mysql.tar.gz"
success "MySQL 数据导入完成"

info "导入 Elasticsearch 数据..."
MSYS_NO_PATHCONV=1 docker run --rm -v "docker_esdata01:/data" -v "${EXPORT_ABS}:/backup:ro" alpine sh -c "cd /data && tar xzf /backup/vol_es.tar.gz"
success "Elasticsearch 数据导入完成"

info "导入 MinIO 数据..."
MSYS_NO_PATHCONV=1 docker run --rm -v "docker_minio_data:/data" -v "${EXPORT_ABS}:/backup:ro" alpine sh -c "cd /data && tar xzf /backup/vol_minio.tar.gz"
success "MinIO 数据导入完成"

info "导入 Redis 数据..."
MSYS_NO_PATHCONV=1 docker run --rm -v "docker_redis_data:/data" -v "${EXPORT_ABS}:/backup:ro" alpine sh -c "cd /data && tar xzf /backup/vol_redis.tar.gz"
success "Redis 数据导入完成"

info "重新启动 RAGFlow..."
cd "$RAGFLOW_DIR"
docker compose up -d
cd ..

info "等待容器完全启动（60 秒）..."
sleep 60
success "RAGFlow 知识库部署完成"

# ── 第 5 步：安装 Python 依赖 ────────────────────────
echo ""
echo "=========================================="
echo " 第 5 步：安装 Python 依赖"
echo "=========================================="

PYTHON_CMD="python"
command -v python3 >/dev/null 2>&1 && PYTHON_CMD="python3"

if [ -f "requirements.txt" ]; then
    info "安装 Python 包..."
    $PYTHON_CMD -m pip install -r requirements.txt -q
    success "Python 依赖安装完成"
else
    warn "未找到 requirements.txt，请手动安装依赖"
fi

# ── 第 6 步：配置环境变量 ────────────────────────────
echo ""
echo "=========================================="
echo " 第 6 步：配置环境变量"
echo "=========================================="

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        info "已从 .env.example 创建 .env"
    fi
fi

echo ""
echo -e "${YELLOW}请编辑 .env 文件，填入以下信息：${NC}"
echo ""
echo "  1. DASHSCOPE_API_KEY  — 通义千问 API Key"
echo "     申请地址: https://dashscope.console.aliyun.com/"
echo ""
echo "  2. RAGFLOW_API_KEY    — RAGFlow API Key"
echo "     获取方式: 访问 http://localhost:80 → 右上角头像 → 用户设置"
echo ""
echo "  3. RAGFLOW_DATASET_IDS — 数据集 ID"
echo "     获取方式: http://localhost:80 → 数据集 → 粮食 → 浏览器地址栏中的 ID"
echo ""

# ── 完成 ─────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e " ${GREEN}部署完成！${NC}"
echo "=========================================="
echo ""
echo " RAGFlow Web UI:  http://localhost:80"
echo " Agent API:       http://localhost:8000"
echo ""
echo " 启动 Agent 后端："
echo "   cd V008"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo " 验证测试："
echo '   curl -X POST http://localhost:8000/api/v1/agent/chat \'
echo '     -H "Content-Type: application/json" \'
echo '     -d '"'"'{"query": "帮我查一下已接入的仓房列表"}'"'"
echo ""
echo "=========================================="
