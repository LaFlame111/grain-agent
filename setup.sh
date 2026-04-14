#!/usr/bin/env bash
#
# Grain Agent V010 — Linux 一键部署脚本
#
# 用法：
#   chmod +x setup.sh
#   sudo ./setup.sh
#
# 在全新 Linux 机器上从零部署：Docker Engine → 镜像导入 → RAGFlow 启动 → Python 环境 → .env 配置
# 幂等设计：每一步先检测是否已完成，重复运行安全

set -euo pipefail

# ─── 常量 ───
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="$PROJECT_ROOT/setup.log"
EXPORT_DIR="$PROJECT_ROOT/ragflow_export"
RAGFLOW_DIR="$PROJECT_ROOT/ragflow_docker"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"

RAGFLOW_IMAGE="infiniflow/ragflow:v0.24.0"
TENANT_ID="589d787629ea11f18fe89f4b88f5c58b"
MYSQL_CONTAINER="ragflow_docker-mysql-1"
MYSQL_USER="root"
MYSQL_PASS="infini_rag_flow"
MYSQL_DB="rag_flow"

RELEASE_TAG="v2.0.0"
RELEASE_URL="https://gitcode.com/api/v5/repos/yekindarly/main/releases/$RELEASE_TAG/attach_files"
RELEASE_FILES=(
    "images.tar.part-aa"
    "images.tar.part-ab"
    "images.tar.part-ac"
    "vol_mysql.tar.gz"
    "vol_es.tar.gz"
    "vol_minio.tar.gz"
    "vol_redis.tar.gz"
)

declare -A VOLUMES=(
    ["ragflow_docker_mysql_data"]="vol_mysql.tar.gz"
    ["ragflow_docker_esdata01"]="vol_es.tar.gz"
    ["ragflow_docker_minio_data"]="vol_minio.tar.gz"
    ["ragflow_docker_redis_data"]="vol_redis.tar.gz"
)

REQUIRED_IMAGES=("infiniflow/ragflow" "mysql" "elasticsearch" "quay.io/minio/minio" "valkey/valkey")
TOTAL_STEPS=9
SETUP_START=$(date +%s)

# ─── 日志系统 ───
log() {
    local level="$1"; shift
    local message="$*"
    local ts
    ts=$(date "+%Y-%m-%d %H:%M:%S")
    local line="[$ts] [$level] $message"

    case "$level" in
        INFO)  echo -e "\033[36m$line\033[0m" ;;
        OK)    echo -e "\033[32m$line\033[0m" ;;
        WARN)  echo -e "\033[33m$line\033[0m" ;;
        ERROR) echo -e "\033[31m$line\033[0m" ;;
        CMD)   echo -e "\033[90m$line\033[0m" ;;
        *)     echo "$line" ;;
    esac
    echo "$line" >> "$LOG_FILE"
}

elapsed() {
    local start=$1
    local now
    now=$(date +%s)
    local diff=$((now - start))
    if [ $diff -ge 60 ]; then
        echo "$((diff / 60))m$((diff % 60))s"
    else
        echo "${diff}s"
    fi
}

step_header() {
    local num=$1
    local title="$2"
    log INFO "--- Step $num/$TOTAL_STEPS: $title ---"
}

# ─── 检查 root ───
if [ "$(id -u)" -ne 0 ]; then
    echo -e "\033[33m[提权] 需要 root 权限，请使用 sudo 运行:\033[0m"
    echo "  sudo $0"
    exit 1
fi

# 检测实际用户（sudo 前的用户），用于非 root 操作
REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~$REAL_USER")

# ─── 开始 ───
log INFO "========== Grain Agent V010 一键部署 (Linux) =========="

# 系统信息
OS_INFO=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'"' -f2 || echo "Unknown")
TOTAL_MEM=$(free -g 2>/dev/null | awk '/Mem:/{print $2}' || echo "?")
DISK_FREE=$(df -BG "$PROJECT_ROOT" 2>/dev/null | awk 'NR==2{print $4}' || echo "?")
log INFO "系统: $OS_INFO | 内存: ${TOTAL_MEM}GB | 磁盘剩余: $DISK_FREE"
log INFO "项目目录: $PROJECT_ROOT"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1: 检测/安装 Docker Engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 1 "检测 Docker Engine"
step_start=$(date +%s)

if docker info &>/dev/null; then
    docker_ver=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
    log OK "Docker Engine 已运行 (v$docker_ver) ($(elapsed $step_start))"
else
    if command -v docker &>/dev/null; then
        log INFO "Docker 已安装但未运行，正在启动..."
        systemctl start docker 2>/dev/null || service docker start 2>/dev/null || true
        sleep 3
    else
        log INFO "Docker 未安装，正在安装..."
        # 检测包管理器
        if command -v apt-get &>/dev/null; then
            log CMD ">>> 使用 apt 安装 Docker"
            apt-get update -qq
            apt-get install -y -qq ca-certificates curl gnupg lsb-release

            # 添加 Docker GPG key 和源
            install -m 0755 -d /etc/apt/keyrings
            if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
                curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
                chmod a+r /etc/apt/keyrings/docker.gpg
            fi

            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list

            apt-get update -qq
            apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
        elif command -v yum &>/dev/null; then
            log CMD ">>> 使用 yum 安装 Docker"
            yum install -y -q yum-utils
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            yum install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
        else
            log ERROR "不支持的包管理器，请手动安装 Docker: https://docs.docker.com/engine/install/"
            exit 1
        fi

        systemctl enable docker
        systemctl start docker

        # 将实际用户加入 docker 组
        usermod -aG docker "$REAL_USER" 2>/dev/null || true
    fi

    # 等待 Docker 就绪
    log INFO "等待 Docker Engine 就绪（最长 60 秒）..."
    waited=0
    while ! docker info &>/dev/null && [ $waited -lt 60 ]; do
        sleep 3
        waited=$((waited + 3))
    done

    if docker info &>/dev/null; then
        docker_ver=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
        log OK "Docker Engine 已就绪 (v$docker_ver) ($(elapsed $step_start))"
    else
        log ERROR "Docker 启动失败！请检查: systemctl status docker"
        exit 1
    fi
fi

# 检查 docker compose 插件
if ! docker compose version &>/dev/null; then
    log ERROR "docker compose 插件不可用，请安装 docker-compose-plugin"
    exit 1
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 2: 检测/安装 Python 3.10+
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 2 "检测 Python 3.10+"
step_start=$(date +%s)

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        major=$(echo "$ver" | cut -d. -f1)
        minor=$(echo "$ver" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -n "$PYTHON" ]; then
    py_ver=$("$PYTHON" --version 2>&1)
    log OK "$py_ver 已安装 ($(elapsed $step_start))"
else
    log INFO "Python 3.10+ 未找到，正在安装..."
    if command -v apt-get &>/dev/null; then
        apt-get update -qq
        apt-get install -y -qq python3 python3-pip python3-venv
    elif command -v yum &>/dev/null; then
        yum install -y -q python3 python3-pip
    else
        log ERROR "请手动安装 Python 3.10+: https://www.python.org/downloads/"
        exit 1
    fi

    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON="$cmd"
                break
            fi
        fi
    done

    if [ -z "$PYTHON" ]; then
        log ERROR "Python 安装后仍找不到 3.10+ 版本"
        exit 1
    fi
    log OK "$($PYTHON --version 2>&1) 安装完成 ($(elapsed $step_start))"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 3: 下载 RAGFlow 镜像和数据（从 GitHub Releases）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 3 "下载 RAGFlow 镜像和数据"
step_start=$(date +%s)

mkdir -p "$EXPORT_DIR"

need_download=false
for f in "${RELEASE_FILES[@]}"; do
    if [ ! -f "$EXPORT_DIR/$f" ]; then
        need_download=true
        break
    fi
done

if $need_download; then
    log INFO "从 GitCode Releases ($RELEASE_TAG) 下载文件..."
    max_retries=3

    for f in "${RELEASE_FILES[@]}"; do
        dest="$EXPORT_DIR/$f"
        if [ -f "$dest" ]; then
            log OK "$f 已存在，跳过"
            continue
        fi

        url="$RELEASE_URL/$f/download"
        downloaded=false

        for attempt in $(seq 1 $max_retries); do
            log INFO "下载 $f（第 ${attempt}/${max_retries} 次）..."
            log CMD ">>> curl -L -C - --retry 3 --retry-delay 5 --progress-bar -o $dest $url"
            if curl -L -C - --retry 3 --retry-delay 5 --progress-bar -o "$dest" "$url" 2>&1 | tee -a "$LOG_FILE"; then
                if [ -f "$dest" ] && [ -s "$dest" ]; then
                    size_mb=$(du -m "$dest" | cut -f1)
                    log OK "$f 下载完成 (${size_mb}MB)"
                    downloaded=true
                    break
                fi
            fi
            log WARN "下载失败"
            [ $attempt -lt $max_retries ] && { log INFO "5 秒后重试..."; sleep 5; }
        done

        if ! $downloaded; then
            log ERROR "文件 $f 下载失败（已重试 $max_retries 次）"
            log ERROR "请检查网络连接，或手动下载: $url"
            exit 1
        fi
    done
    log OK "所有文件下载完成 ($(elapsed $step_start))"
else
    log OK "ragflow_export/ 文件已齐全，跳过下载 ($(elapsed $step_start))"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 4: 导入 Docker 镜像
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 4 "导入 Docker 镜像"
step_start=$(date +%s)

# 检查是否已导入
all_present=true
existing_images=$(docker images --format "{{.Repository}}" 2>/dev/null)
for img in "${REQUIRED_IMAGES[@]}"; do
    if ! echo "$existing_images" | grep -qF "$img"; then
        all_present=false
        break
    fi
done

if $all_present; then
    log OK "所有镜像已存在，跳过导入 ($(elapsed $step_start))"
else
    images_tar="$EXPORT_DIR/images.tar"

    # 如果 images.tar 不存在但分卷存在，先合并
    if [ ! -f "$images_tar" ]; then
        parts=$(ls "$EXPORT_DIR"/images.tar.part-* 2>/dev/null | sort)
        if [ -n "$parts" ]; then
            part_count=$(echo "$parts" | wc -l)
            log INFO "合并分卷文件 ($part_count 个分卷)..."
            cat $EXPORT_DIR/images.tar.part-* > "$images_tar"
            size_mb=$(du -m "$images_tar" | cut -f1)
            log OK "分卷合并完成 (${size_mb}MB)"
        else
            log ERROR "找不到 ragflow_export/images.tar 或分卷文件！"
            exit 1
        fi
    fi

    log INFO "正在导入镜像（可能需要几分钟）..."
    log CMD ">>> docker load -i $images_tar"
    docker load -i "$images_tar" 2>&1 | tee -a "$LOG_FILE"

    # 验证
    existing_images=$(docker images --format "{{.Repository}}:{{.Tag}}" 2>/dev/null)
    verified=0
    for img in "${REQUIRED_IMAGES[@]}"; do
        if echo "$existing_images" | grep -qF "$img"; then
            verified=$((verified + 1))
        else
            log WARN "镜像未找到: $img"
        fi
    done
    log OK "镜像导入完成 ($verified/${#REQUIRED_IMAGES[@]} 镜像验证通过) ($(elapsed $step_start))"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 5: 首次启动 RAGFlow（创建数据卷）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 5 "首次启动 RAGFlow（创建数据卷）"
step_start=$(date +%s)

# 检查数据卷是否已存在
vol_list=$(docker volume ls --format "{{.Name}}" 2>/dev/null)
all_volumes_exist=true
for vol in "${!VOLUMES[@]}"; do
    if ! echo "$vol_list" | grep -qF "$vol"; then
        all_volumes_exist=false
        break
    fi
done

if $all_volumes_exist; then
    log OK "数据卷已存在，跳过首次启动 ($(elapsed $step_start))"
else
    log INFO "启动 Docker Compose 以创建数据卷..."
    cd "$RAGFLOW_DIR"
    docker compose up -d 2>&1 | tee -a "$LOG_FILE"

    # 等待 MySQL healthy
    log INFO "等待 MySQL 容器就绪（最长 2 分钟）..."
    waited=0
    mysql_ready=false
    while [ $waited -lt 120 ]; do
        if docker compose ps 2>/dev/null | grep -q "mysql.*healthy"; then
            mysql_ready=true
            break
        fi
        sleep 5
        waited=$((waited + 5))
        printf "."
    done
    echo ""

    if $mysql_ready; then
        log OK "MySQL 容器就绪"
    else
        log WARN "MySQL 容器未报告 healthy，继续尝试..."
    fi

    log INFO "停止容器（保留数据卷）..."
    docker compose down 2>&1 | tee -a "$LOG_FILE"
    cd "$PROJECT_ROOT"
    log OK "数据卷已创建 ($(elapsed $step_start))"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 6: 导入数据卷（知识库数据）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 6 "导入数据卷（知识库数据）"
step_start=$(date +%s)

# 检查 MySQL 数据卷是否已有数据
skip_import=false
file_count=$(docker run --rm -v "ragflow_docker_mysql_data:/data:ro" "$RAGFLOW_IMAGE" sh -c "ls /data/ 2>/dev/null | wc -l" 2>/dev/null || echo "0")
if [ "$file_count" -gt 5 ]; then
    skip_import=true
fi

if $skip_import; then
    log OK "数据卷已有数据，跳过导入 ($(elapsed $step_start))"
else
    export_path=$(cd "$EXPORT_DIR" && pwd)

    for vol in "${!VOLUMES[@]}"; do
        tar_file="${VOLUMES[$vol]}"
        tar_path="$EXPORT_DIR/$tar_file"

        if [ ! -f "$tar_path" ]; then
            log WARN "跳过 $vol: 文件 $tar_file 不存在"
            continue
        fi

        log INFO "导入 $vol <- $tar_file ..."
        docker run --rm \
            -v "$vol:/data" \
            -v "$export_path:/backup:ro" \
            "$RAGFLOW_IMAGE" sh -c "cd /data && tar xzf /backup/$tar_file" 2>&1 | tee -a "$LOG_FILE"
    done
    log OK "数据卷导入完成 ($(elapsed $step_start))"
fi

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 7: 启动 RAGFlow（带数据）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 7 "启动 RAGFlow（带数据）"
step_start=$(date +%s)

cd "$RAGFLOW_DIR"
docker compose up -d 2>&1 | tee -a "$LOG_FILE"

# 等待所有容器就绪
log INFO "等待所有容器就绪（最长 3 分钟）..."
waited=0
all_healthy=false
while [ $waited -lt 180 ]; do
    ps_output=$(docker compose ps 2>/dev/null)
    running_count=$(echo "$ps_output" | grep -c "running\|healthy" || true)
    if [ "$running_count" -ge 3 ]; then
        unhealthy=$(echo "$ps_output" | grep -v "healthy\|running\|NAME\|^$" | head -1 || true)
        if [ -z "$unhealthy" ]; then
            all_healthy=true
            break
        fi
    fi
    sleep 5
    waited=$((waited + 5))
    printf "."
done
echo ""

if $all_healthy; then
    log OK "所有容器已就绪"
else
    log WARN "部分容器可能未完全就绪，继续..."
    docker compose ps 2>&1 | tee -a "$LOG_FILE"
fi

# 验证 RAGFlow API 可达
log INFO "验证 RAGFlow API..."
ragflow_ready=false
waited=0
while [ $waited -lt 60 ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:9380 2>/dev/null | grep -qE "^[1-4]"; then
        ragflow_ready=true
        break
    fi
    sleep 5
    waited=$((waited + 5))
done

if $ragflow_ready; then
    log OK "RAGFlow API 可达 (http://localhost:9380) ($(elapsed $step_start))"
else
    log WARN "RAGFlow API 暂时不可达，可能需要更长启动时间"
fi

cd "$PROJECT_ROOT"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 8: Python 依赖 + .env 配置
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 8 "安装 Python 依赖 + 配置 .env"
step_start=$(date +%s)

# 安装 Python 依赖
log INFO "安装 Python 依赖..."
$PYTHON -m pip install -r "$PROJECT_ROOT/requirements.txt" -q 2>&1 | tee -a "$LOG_FILE"
log OK "Python 依赖安装完成"

# .env 配置
if [ ! -f "$ENV_FILE" ]; then
    log INFO "创建 .env 配置文件..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

# 读取当前 DASHSCOPE_API_KEY
current_key=$(grep -oP 'DASHSCOPE_API_KEY=\K.+' "$ENV_FILE" 2>/dev/null || echo "")

if [ -z "$current_key" ] || [ "$current_key" = "你的通义千问API_Key" ]; then
    echo ""
    echo -e "\033[36m============================================\033[0m"
    echo -e "\033[36m 请输入通义千问 API Key (DASHSCOPE_API_KEY)\033[0m"
    echo -e "\033[36m 申请地址: https://dashscope.console.aliyun.com/\033[0m"
    echo -e "\033[36m============================================\033[0m"
    read -rp "DASHSCOPE_API_KEY: " api_key
    if [ -n "$api_key" ]; then
        sed -i "s|DASHSCOPE_API_KEY=.*|DASHSCOPE_API_KEY=$api_key|" "$ENV_FILE"
        log OK "DASHSCOPE_API_KEY 已写入"
    else
        log WARN "未输入 API Key，请稍后手动编辑 .env 文件"
    fi
else
    log OK "DASHSCOPE_API_KEY 已配置"
fi

# 自动获取 RAGFlow API Key 和数据集 ID
log INFO "自动配置 RAGFlow API Key 和数据集 ID..."

# 等待 MySQL 容器可用
mysql_ok=false
waited=0
while [ $waited -lt 30 ]; do
    if docker exec "$MYSQL_CONTAINER" mysqladmin -u"$MYSQL_USER" -p"$MYSQL_PASS" ping 2>/dev/null | grep -q "alive"; then
        mysql_ok=true
        break
    fi
    sleep 3
    waited=$((waited + 3))
done

if $mysql_ok; then
    # 生成 API Token
    token_uuid=$(cat /proc/sys/kernel/random/uuid | tr -d '-')
    api_token="ragflow-$token_uuid"
    now_ms=$(date +%s%3N)
    now_dt=$(date "+%Y-%m-%d %H:%M:%S")

    sql="INSERT INTO api_token (create_time, create_date, update_time, update_date, tenant_id, token, source) VALUES ($now_ms, '$now_dt', $now_ms, '$now_dt', '$TENANT_ID', '$api_token', 'markdown');"

    log CMD "创建 RAGFlow API Token..."
    insert_result=$(docker exec "$MYSQL_CONTAINER" mysql -u"$MYSQL_USER" -p"$MYSQL_PASS" "$MYSQL_DB" -e "$sql" 2>&1 || true)
    echo "$insert_result" >> "$LOG_FILE"

    if ! echo "$insert_result" | grep -qi "ERROR"; then
        log OK "RAGFlow API Token 已创建"

        # 写入 .env
        sed -i "s|RAGFLOW_API_KEY=.*|RAGFLOW_API_KEY=$api_token|" "$ENV_FILE"

        # 获取数据集 ID
        sleep 2
        ds_resp=$(curl -s -H "Authorization: Bearer $api_token" "http://localhost:9380/api/v1/datasets?page=1&page_size=30" 2>/dev/null || echo "")

        if [ -n "$ds_resp" ]; then
            ds_code=$(echo "$ds_resp" | $PYTHON -c "import sys,json; print(json.load(sys.stdin).get('code',1))" 2>/dev/null || echo "1")
            if [ "$ds_code" = "0" ]; then
                dataset_ids=$($PYTHON -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
print(','.join(d['id'] for d in data))
for d in data:
    print(f\"  数据集: {d.get('name','')} (ID: {d.get('id','')}, 文档数: {d.get('doc_num',0)})\", file=sys.stderr)
" <<< "$ds_resp" 2>&1 1>/dev/null || echo "")

                # 重新获取 ids（stdout）
                ids_only=$($PYTHON -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
print(','.join(d['id'] for d in data))
" <<< "$ds_resp" 2>/dev/null || echo "")

                if [ -n "$ids_only" ]; then
                    sed -i "s|RAGFLOW_DATASET_IDS=.*|RAGFLOW_DATASET_IDS=$ids_only|" "$ENV_FILE"
                    log OK "数据集 ID 已写入: $ids_only"
                    # 打印数据集信息
                    $PYTHON -c "
import sys, json
data = json.load(sys.stdin).get('data', [])
for d in data:
    print(f\"  数据集: {d.get('name','')} (ID: {d.get('id','')}, 文档数: {d.get('doc_num',0)})\")
" <<< "$ds_resp" 2>/dev/null | while read -r line; do log INFO "$line"; done
                else
                    log WARN "未找到数据集，请稍后手动配置 RAGFLOW_DATASET_IDS"
                fi
            else
                log WARN "数据集查询返回异常"
            fi
        else
            log WARN "数据集查询失败，RAGFlow 可能需要更长启动时间，请稍后运行:"
            log WARN "  $PYTHON setup_apitoken.py"
        fi
    else
        log WARN "Token 写入失败，请稍后手动运行: $PYTHON setup_apitoken.py"
    fi
else
    log WARN "MySQL 容器不可用，跳过自动配置。请稍后手动运行: $PYTHON setup_apitoken.py"
fi

log OK "配置完成 ($(elapsed $step_start))"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 9: 输出总结
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
step_header 9 "完成"

total_elapsed=$(elapsed $SETUP_START)

echo ""
echo -e "\033[32m==========================================\033[0m"
echo -e "\033[32m Grain Agent V010 — 部署完成！\033[0m"
echo -e "\033[32m==========================================\033[0m"
echo ""
echo -e "\033[36m RAGFlow Web UI:  http://localhost:80\033[0m"
echo -e "\033[36m RAGFlow API:     http://localhost:9380\033[0m"
echo ""
echo " 启动 Agent:"
echo "   bash start.sh"
echo ""
echo " 停止 Agent:"
echo "   bash stop.sh"
echo ""
echo -e "\033[36m 前端: http://127.0.0.1:8000/ui (Agent 启动后)\033[0m"
echo ""
echo -e "\033[90m 日志: $LOG_FILE\033[0m"
echo -e "\033[90m 总耗时: $total_elapsed\033[0m"
echo -e "\033[32m==========================================\033[0m"
echo ""

log OK "========== 部署完成 (总耗时 $total_elapsed) =========="
