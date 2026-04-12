#!/bin/bash
# ============================================================
# 分卷打包 + 上传到 GitHub Releases 的脚本
#
# 此脚本供你（发布者）使用，对方不需要此脚本。
#
# 前提：
#   1. 安装 GitHub CLI: https://cli.github.com/
#   2. 已登录: gh auth login
#   3. 已创建 GitHub 仓库并 push 代码
#
# 用法：在 V008 目录下执行：
#   bash split-and-upload.sh
# ============================================================

set -e

# ── 配置（修改为你的实际值） ─────────────────────────
GITHUB_REPO="LaFlame111/grain-agent"
RELEASE_TAG="v1.0.0"
RELEASE_TITLE="Grain Agent V008 完整部署包"

RAGFLOW_EXPORT="D:/ragflow_export"             # 导出包路径
RAGFLOW_DOCKER="C:/Users/ASUS/Desktop/ragflow/docker"  # RAGFlow docker 配置路径
SPLIT_DIR="./release_parts"                    # 分卷临时目录
SPLIT_SIZE="1900m"                             # 每个分卷大小（留余量）

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

# ── 检查工具 ─────────────────────────────────────────
command -v gh >/dev/null 2>&1 || error "未找到 gh (GitHub CLI)，请先安装: https://cli.github.com/"
command -v split >/dev/null 2>&1 || error "未找到 split 命令"

# 检查登录状态
gh auth status >/dev/null 2>&1 || error "GitHub CLI 未登录，请执行: gh auth login"

echo ""
echo "=========================================="
echo " 分卷打包 + 上传到 GitHub Releases"
echo "=========================================="
echo " 仓库: ${GITHUB_REPO}"
echo " Tag:  ${RELEASE_TAG}"
echo "=========================================="
echo ""

# ── 第 1 步：分卷 images.tar ────────────────────────
info "第 1 步：将 images.tar（~4GB）分卷为 <2GB 的块..."

mkdir -p "$SPLIT_DIR"

IMAGES_TAR="${RAGFLOW_EXPORT}/images.tar"
[ -f "$IMAGES_TAR" ] || error "未找到 ${IMAGES_TAR}"

# 分卷（生成 images.tar.part-aa, images.tar.part-ab, ...）
split -b "$SPLIT_SIZE" -d -a 2 "$IMAGES_TAR" "${SPLIT_DIR}/images.tar.part-" \
    || split -b "$SPLIT_SIZE" "$IMAGES_TAR" "${SPLIT_DIR}/images.tar.part-"

PART_COUNT=$(ls "${SPLIT_DIR}"/images.tar.part-* 2>/dev/null | wc -l)
success "分卷完成，共 ${PART_COUNT} 个分卷"

# 显示分卷文件
ls -lh "${SPLIT_DIR}"/images.tar.part-*

# ── 第 2 步：复制其他文件 ────────────────────────────
info "第 2 步：复制数据卷和 docker compose 文件..."

# 数据卷
cp "${RAGFLOW_EXPORT}/vol_mysql.tar.gz"  "${SPLIT_DIR}/"
cp "${RAGFLOW_EXPORT}/vol_es.tar.gz"     "${SPLIT_DIR}/"
cp "${RAGFLOW_EXPORT}/vol_minio.tar.gz"  "${SPLIT_DIR}/"
cp "${RAGFLOW_EXPORT}/vol_redis.tar.gz"  "${SPLIT_DIR}/"

# docker compose 配置文件
cp "${RAGFLOW_DOCKER}/docker-compose.yml"           "${SPLIT_DIR}/"
cp "${RAGFLOW_DOCKER}/docker-compose-base.yml"      "${SPLIT_DIR}/"
cp "${RAGFLOW_DOCKER}/entrypoint.sh"                "${SPLIT_DIR}/"
cp "${RAGFLOW_DOCKER}/service_conf.yaml.template"   "${SPLIT_DIR}/"
cp "${RAGFLOW_DOCKER}/init.sql"                     "${SPLIT_DIR}/"

success "文件复制完成"

# 显示所有待上传文件
echo ""
info "待上传文件清单："
ls -lh "${SPLIT_DIR}/"
echo ""

TOTAL_SIZE=$(du -sh "${SPLIT_DIR}" | cut -f1)
info "总大小: ${TOTAL_SIZE}"
echo ""

# ── 第 3 步：创建 Release 并上传 ────────────────────
info "第 3 步：创建 GitHub Release 并上传文件..."
warn "上传约 4.5GB 文件，耗时取决于网络速度"
echo ""

# 创建 release（如果不存在）
if gh release view "$RELEASE_TAG" --repo "$GITHUB_REPO" >/dev/null 2>&1; then
    warn "Release ${RELEASE_TAG} 已存在，将追加文件"
else
    info "创建 Release ${RELEASE_TAG}..."
    gh release create "$RELEASE_TAG" \
        --repo "$GITHUB_REPO" \
        --title "$RELEASE_TITLE" \
        --notes "$(cat <<'EOF'
## 粮情分析智能体 V008 完整部署包

### 包含内容
- Docker 镜像（RAGFlow v0.24.0 + MySQL + ES + MinIO + Redis）
- 已解析知识库数据卷（167 个粮储标准文档，4001 chunks）
- RAGFlow docker-compose 配置文件

### 部署方法
```bash
git clone https://github.com/REPO_PLACEHOLDER.git
cd grain-agent/V008
bash deploy.sh
```

详见仓库中的 `交付部署指南.md`。
EOF
)"
    success "Release 创建成功"
fi

# 逐个上传文件
info "开始上传文件..."
for file in "${SPLIT_DIR}"/*; do
    filename=$(basename "$file")
    filesize=$(du -h "$file" | cut -f1)
    info "上传 ${filename} (${filesize})..."

    gh release upload "$RELEASE_TAG" "$file" \
        --repo "$GITHUB_REPO" \
        --clobber

    success "${filename} 上传完成"
done

# ── 完成 ─────────────────────────────────────────────
echo ""
echo "=========================================="
echo -e " ${GREEN}全部上传完成！${NC}"
echo "=========================================="
echo ""
echo " Release 地址："
echo "   https://github.com/${GITHUB_REPO}/releases/tag/${RELEASE_TAG}"
echo ""
echo " 对方部署方法："
echo "   git clone https://github.com/${GITHUB_REPO}.git"
echo "   cd grain-agent/V008"
echo "   bash deploy.sh"
echo ""

# ── 清理提示 ─────────────────────────────────────────
echo -e "${YELLOW}提示：${NC}上传完成后可删除临时分卷目录："
echo "   rm -rf ${SPLIT_DIR}"
echo ""
