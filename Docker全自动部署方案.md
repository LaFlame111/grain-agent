# Grain Agent V010 — Docker 全自动一键部署方案

## 概述

纯 PowerShell 一键部署方案，在全新 Windows 11 机器上从零到运行：WSL2 → Docker Desktop → 镜像导入 → RAGFlow 启动 → 数据导入 → Python 环境 → 自动配置 API Key。

**不依赖 bash/WSL 执行部署命令**，Docker CLI 在 Windows 上原生可用。镜像和数据全部离线（`ragflow_export/` 目录已包含），不需要从 GitHub Releases 下载。

---

## 用户体验

```
1. git clone https://github.com/LaFlame111/grain-agent.git
2. 右键 setup.ps1 → "以管理员身份运行"
3.（若首次启用 WSL2）重启后再运行一次 setup.ps1
4. 等待自动完成（5~15 分钟）
5. 按提示输入 DASHSCOPE_API_KEY（通义千问）
6. 脚本自动获取 RAGFlow API Key 和数据集 ID 并写入 .env
7. 运行 .\start_server.ps1 启动 Agent
8. 浏览器打开 http://127.0.0.1:8000/ui
```

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `setup.ps1` | **核心脚本** | PowerShell 一键部署入口（~400 行） |
| `Docker全自动部署方案.md` | **本文档** | 方案设计说明 |
| `交付部署指南.md` | 简化版 | 面向用户的快速部署指南 |

**不动的文件**（已经够好）：

- `start.sh` / `stop.sh` — Bash 启停脚本
- `start_server.ps1` / `stop_server.ps1` — PowerShell 启停脚本
- `ragflow_docker/*` — RAGFlow Docker Compose 配置
- `ragflow_export/*` — 预打包的镜像和数据卷
- `.env.example` — 环境变量模板

---

## setup.ps1 设计

### 设计原则

| 原则 | 说明 |
|------|------|
| 纯 PowerShell | 不依赖 WSL/bash/Git Bash，Docker CLI 在 Windows 上原生可用 |
| 幂等 | 每一步先检测是否已完成，重复运行安全 |
| 重启恢复 | `.setup_state` 文件记录进度，WSL2 启用后重启可续跑 |
| 离线优先 | 镜像和数据都在 `ragflow_export/`，不需要网络（除安装 Docker/Python） |
| 全程日志 | 输出到控制台 + `setup.log` 文件，部署失败可排查 |

### 日志系统

脚本启动时创建 `setup.log`（项目根目录），所有输出同时写入控制台和日志文件。

```powershell
function Log {
    param([string]$Level, [string]$Message)
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$ts] [$Level] $Message"
    switch ($Level) {
        "INFO"  { Write-Host $line -ForegroundColor Cyan }
        "OK"    { Write-Host $line -ForegroundColor Green }
        "WARN"  { Write-Host $line -ForegroundColor Yellow }
        "ERROR" { Write-Host $line -ForegroundColor Red }
        "CMD"   { Write-Host $line -ForegroundColor DarkGray }
    }
    $line | Out-File -Append -FilePath $LogFile -Encoding utf8
}
```

**日志文件示例**：
```
[2026-04-15 10:00:00] [INFO] ========== Grain Agent V010 一键部署 ==========
[2026-04-15 10:00:00] [INFO] 系统: Windows 11 Home 22621 | 内存: 16GB | 磁盘剩余: 120GB
[2026-04-15 10:00:00] [INFO] --- Step 1/10: 检测 WSL2 ---
[2026-04-15 10:00:01] [OK]   WSL2 已启用
[2026-04-15 10:00:01] [INFO] --- Step 2/10: 检测 Docker Desktop ---
[2026-04-15 10:00:02] [OK]   Docker Desktop 已运行 (v4.38.0)
[2026-04-15 10:00:02] [INFO] --- Step 5/10: 导入 Docker 镜像 ---
[2026-04-15 10:00:02] [CMD]  >>> docker load -i images.tar
[2026-04-15 10:03:45] [OK]   镜像导入完成 (耗时 3m43s)
...
[2026-04-15 10:12:30] [INFO] ========== 部署完成 (总耗时 12m30s) ==========
```

部署失败时用户只需把 `setup.log` 发来，即可看到完整的命令执行过程和具体在哪一步失败。

---

### 流程（10 步）

#### Step 0: 管理员自提权
- 检测是否以管理员运行
- 未提权 → `Start-Process powershell -Verb RunAs` 自动提升

#### Step 1: 检测/启用 WSL2
- `wsl --status` 检测
- 未启用 → `dism.exe` 启用 WSL + 虚拟机平台 → 写 `.setup_state = "need_reboot"` → 提示重启
- 已启用或重启后 → 继续

#### Step 2: 检测/安装 Docker Desktop
- `docker info` 检测是否可用
- 未安装 → 下载 Docker Desktop 安装包 (~600MB) → 静默安装
- 已安装未运行 → 启动 Docker Desktop → 轮询等待 `docker info` 成功（最长 3 分钟）

#### Step 3: WSL2 内存配置
- 检测 `~\.wslconfig` 是否已配置 `memory=12GB`
- 未配置 → 写入 → `wsl --shutdown` → 等待 Docker 重新就绪

#### Step 4: 检测/安装 Python 3.10+
- `python --version` 检测
- 未安装或版本过低 → 下载 Python 3.12 安装包 → 静默安装（PrependPath=1）
- 刷新 PATH

#### Step 5: 导入 Docker 镜像
- 检测 `docker images` 是否已有所需镜像
- 未导入：
  - 若 `ragflow_export/images.tar` 不存在但分卷 `.part-*` 存在 → 用 PowerShell 流式合并
  - `docker load -i ragflow_export\images.tar`
- 验证 5 个镜像：ragflow, mysql, elasticsearch, minio, valkey

#### Step 6: 首次启动 RAGFlow（创建数据卷）
- `cd ragflow_docker && docker compose up -d`
- 等待 MySQL 容器 healthy（轮询，最长 2 分钟）
- `docker compose down`

> **为什么要先启动再停？** Docker Compose 自动创建带项目名前缀的数据卷（`ragflow_docker_mysql_data` 等），这是确保卷名正确的最简单方式。

#### Step 7: 导入数据卷（核心步骤）
- **用 RAGFlow 镜像代替 alpine**（`infiniflow/ragflow:v0.24.0` 基于 Ubuntu，有 `tar`）
- 4 个数据卷，名称与 Docker Compose 项目前缀匹配：

```powershell
$volumes = @{
    "ragflow_docker_mysql_data" = "vol_mysql.tar.gz"
    "ragflow_docker_esdata01"   = "vol_es.tar.gz"
    "ragflow_docker_minio_data" = "vol_minio.tar.gz"
    "ragflow_docker_redis_data" = "vol_redis.tar.gz"
}

foreach ($vol in $volumes.GetEnumerator()) {
    docker run --rm `
        -v "$($vol.Key):/data" `
        -v "${exportPath}:/backup:ro" `
        $RAGFLOW_IMAGE sh -c "cd /data && tar xzf /backup/$($vol.Value)"
}
```

#### Step 8: 启动 RAGFlow（带数据）
- `cd ragflow_docker && docker compose up -d`
- 等待所有容器 healthy（轮询最长 3 分钟）
- 验证：`http://localhost:9380` 可达

#### Step 9: Python 依赖 + .env 配置
- `python -m pip install -r requirements.txt -q`
- 若 `.env` 不存在 → 复制 `.env.example`
- 交互式询问 `DASHSCOPE_API_KEY` → 写入 `.env`
- **自动获取 RAGFlow API Key 和数据集 ID**：
  1. `docker exec ragflow_docker-mysql-1 mysql ...` 生成 token
  2. INSERT 到 `api_token` 表
  3. 调用 `/api/v1/datasets` 获取数据集列表
  4. 自动写入 `.env`

#### Step 10: 输出总结
```
==========================================
 Grain Agent V010 — 部署完成！
==========================================

 RAGFlow Web UI:  http://localhost:80
 RAGFlow API:     http://localhost:9380

 启动 Agent:
   .\start_server.ps1         (PowerShell)
   bash start.sh              (Git Bash)

 前端: http://127.0.0.1:8000/ui (Agent 启动后)
==========================================
```

---

## 关键设计决策

| 决策 | 原因 |
|------|------|
| 用 RAGFlow 镜像代替 alpine 做数据卷导入 | alpine 不在 images.tar 里，网络可能不通 |
| 先启动再停止 Docker Compose 来创建卷 | 确保卷名前缀 `ragflow_docker_` 与 Compose 一致 |
| 纯 PowerShell 不依赖 bash | 避免 MSYS 路径转换 bug，Docker CLI 在 Windows 原生可用 |
| `.setup_state` 文件恢复重启 | WSL2 启用必须重启，用户不用记住跑到哪了 |
| 自动通过 MySQL 创建 RAGFlow token | 省去用户手动在 Web UI 里找 API Key 和数据集 ID |

---

## 与旧方案的区别

| 对比项 | 旧方案 (`deploy.sh`) | 新方案 (`setup.ps1`) |
|--------|----------------------|----------------------|
| 执行环境 | bash（需 WSL/Git Bash） | 纯 PowerShell（Windows 原生） |
| 镜像来源 | GitHub Releases 下载 | 本地 `ragflow_export/` |
| 数据卷导入 | 用 alpine 镜像 | 用 RAGFlow 镜像 |
| 数据卷名称 | `docker_*`（有 bug） | `ragflow_docker_*`（与 Compose 一致） |
| API Key | 手动到 Web UI 获取 | 自动通过 MySQL 创建 |
| 路径处理 | MSYS 路径转换 + `pwd -W` | Windows 原生路径 |
| 日志 | 控制台输出 | 控制台 + setup.log 文件 |
| 重启恢复 | 无 | `.setup_state` 续跑 |

---

## 验证方法

1. 在一台**全新 Windows 11** 机器上（无 Docker、无 Python）
2. `git clone` 项目，右键 `setup.ps1` → 以管理员身份运行
3. 若提示重启 → 重启后再运行 `setup.ps1`
4. 等待脚本自动完成
5. 输入 DASHSCOPE_API_KEY
6. 运行 `.\start_server.ps1`
7. 浏览器打开 `http://127.0.0.1:8000/ui`
8. 输入 "帮我查一下已接入的仓房列表" → 确认返回正常
9. 输入 "储粮温度管理有哪些规定？" → 确认 RAG 知识检索有结果

---

## 注意事项

1. **重启问题**：首次运行如果 WSL2 未启用，需要重启一次电脑。脚本自动记录状态，重启后再次运行即可续跑。
2. **Docker Desktop 许可**：个人和小团队免费，大公司（>250 人或年收入 >$10M）需要付费许可。
3. **网络要求**：仅下载 Docker Desktop (~600MB) 和 Python (~30MB) 需要网络，镜像和数据全部离线。
4. **磁盘空间**：RAGFlow 完整部署约占 10-15GB。
5. **内存**：建议 16GB+，WSL2 分配 12GB。
