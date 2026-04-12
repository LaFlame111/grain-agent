# GitHub 发布操作指南

本文档指导你如何将 Grain Agent V008 发布到 GitHub，让对方可以一键部署。

## 整体流程

```
你的操作                              对方的操作
─────────                            ─────────
1. 创建 GitHub 仓库                   1. git clone
2. push 源码                          2. cd V008 && bash deploy.sh
3. 运行 split-and-upload.sh           3. 编辑 .env 填入 API Key
   → 自动上传到 Releases              4. 启动 Agent 后端
```

## 前提准备

### 安装 GitHub CLI

```bash
# Windows (winget)
winget install --id GitHub.cli

# 或从官网下载: https://cli.github.com/
```

### 登录 GitHub

```bash
gh auth login
# 选择 GitHub.com → HTTPS → 浏览器认证
```

## 第 1 步：创建 GitHub 仓库

```bash
# 在 V008 目录下初始化 git
cd C:/Users/ASUS/Desktop/grain_agent-ubuntu/V008

git init
git add .
git commit -m "Grain Agent V008 初始发布"

# 创建远程仓库（选择 public 或 private）
gh repo create grain-agent --public --source=. --push
```

> 如果选 private，对方需要你添加为 collaborator 才能访问。

### 仓库结构（对方看到的）

```
grain-agent/
├── .env.example          ← 环境变量模板
├── .gitignore
├── deploy.sh             ← 对方执行的一键部署脚本
├── requirements.txt      ← Python 依赖
├── app/                  ← Agent 后端源码
│   ├── main.py
│   ├── services/
│   ├── core/
│   ├── api/
│   └── models/
├── data/
│   ├── knowledge/        ← 知识库原始文档（备份）
│   └── eval/             ← 评估测试集
├── 交付部署指南.md
├── RAG升级.md
├── README.md
└── ...
```

## 第 2 步：上传大文件到 Releases

### 方法 A：一键脚本（推荐）

**编辑 `split-and-upload.sh`，修改第 18-19 行的仓库名：**

```bash
GITHUB_REPO="你的GitHub用户名/grain-agent"   # ← 改这里
RELEASE_TAG="v1.0.0"
```

**然后执行：**

```bash
bash split-and-upload.sh
```

脚本会自动：
1. 将 images.tar（4GB）分卷为 3 个 <2GB 文件
2. 复制数据卷和 docker compose 配置
3. 创建 GitHub Release
4. 逐个上传所有文件（共约 4.5GB）

### 方法 B：手动操作

```bash
# 1. 分卷
split -b 1900m D:/ragflow_export/images.tar ./images.tar.part-

# 2. 创建 release
gh release create v1.0.0 --title "V008 完整部署包"

# 3. 逐个上传
gh release upload v1.0.0 images.tar.part-aa
gh release upload v1.0.0 images.tar.part-ab
gh release upload v1.0.0 images.tar.part-ac
gh release upload v1.0.0 D:/ragflow_export/vol_mysql.tar.gz
gh release upload v1.0.0 D:/ragflow_export/vol_es.tar.gz
gh release upload v1.0.0 D:/ragflow_export/vol_minio.tar.gz
gh release upload v1.0.0 D:/ragflow_export/vol_redis.tar.gz

# 4. 上传 docker compose 配置
gh release upload v1.0.0 C:/Users/ASUS/Desktop/ragflow/docker/docker-compose.yml
gh release upload v1.0.0 C:/Users/ASUS/Desktop/ragflow/docker/docker-compose-base.yml
gh release upload v1.0.0 C:/Users/ASUS/Desktop/ragflow/docker/entrypoint.sh
gh release upload v1.0.0 C:/Users/ASUS/Desktop/ragflow/docker/service_conf.yaml.template
gh release upload v1.0.0 C:/Users/ASUS/Desktop/ragflow/docker/init.sql
```

## 第 3 步：更新 deploy.sh 配置

上传完成后，**编辑 `deploy.sh` 第 18-19 行**，将仓库名和 tag 改为实际值：

```bash
GITHUB_REPO="你的GitHub用户名/grain-agent"   # ← 改这里
RELEASE_TAG="v1.0.0"
```

然后提交并 push：

```bash
git add deploy.sh
git commit -m "更新 deploy.sh 中的仓库配置"
git push
```

## 第 4 步：验证

在另一台机器上（或删除本地 clone 重新操作）：

```bash
git clone https://github.com/你的用户名/grain-agent.git
cd grain-agent
bash deploy.sh
```

确认流程能完整走通。

## 需要告知对方的信息

部署完成后对方还需要：

1. **通义千问 API Key** — 对方自行在 https://dashscope.console.aliyun.com/ 申请
2. **RAGFlow 登录密码** — 你原始注册时的邮箱和密码（或让对方在 RAGFlow Web UI 注册新账号）
3. **WMS 接口** — 确认 WMS 服务器 `121.40.162.1:8017` 对对方网络可达

## 上传耗时估算

| 文件 | 大小 | 10Mbps 上传 | 50Mbps 上传 |
|------|------|------------|------------|
| images.tar 分卷 ×3 | ~4.0 GB | ~55 分钟 | ~11 分钟 |
| vol_minio.tar.gz | ~339 MB | ~4.5 分钟 | ~1 分钟 |
| vol_es.tar.gz | ~76 MB | ~1 分钟 | ~12 秒 |
| vol_mysql.tar.gz | ~16 MB | ~13 秒 | ~3 秒 |
| 其他小文件 | ~1 MB | 几秒 | 几秒 |
| **合计** | **~4.5 GB** | **~60 分钟** | **~13 分钟** |

## 常见问题

### Q: GitHub Releases 文件大小限制？
A: 单文件最大 2GB。images.tar 约 4GB，所以需要分卷为 <2GB 的块。

### Q: 对方网速慢怎么办？
A: GitHub Releases 支持断点续传（curl -C -）。deploy.sh 会跳过已下载的文件，可以中断后重试。

### Q: 仓库设为 private 可以吗？
A: 可以，但对方需要：
- 你在仓库 Settings → Collaborators 添加对方 GitHub 账号
- 对方需要 `gh auth login` 认证后才能 clone 和下载 Releases

### Q: 上传中断了怎么办？
A: 重新运行 `split-and-upload.sh`，它会使用 `--clobber` 覆盖已有文件。

### Q: 不想用 GitHub，有替代方案吗？
A: 可以用：
- **阿里云 OSS** — 国内速度快，修改 deploy.sh 中的下载 URL 即可
- **百度网盘 / 阿里云盘** — 手动分享链接，对方手动下载后执行 deploy.sh（跳过下载步骤）
- **U 盘拷贝** — 直接把 ragflow_export/ + V008/ 拷贝给对方
