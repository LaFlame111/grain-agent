#Requires -Version 5.1
<#
.SYNOPSIS
    Grain Agent V010 — Windows 一键部署脚本
.DESCRIPTION
    在全新 Windows 11 机器上从零部署：WSL2 → Docker Desktop → 镜像导入 → RAGFlow 启动 → Python 环境 → .env 配置
    右键此文件 → "以管理员身份运行"
.NOTES
    幂等设计：每一步先检测是否已完成，重复运行安全
    重启恢复：用 .setup_state 记录进度，WSL2 启用后重启可续跑
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # 加速 Invoke-WebRequest

# ─── 常量 ───
$PROJECT_ROOT = $PSScriptRoot
$LOG_FILE     = Join-Path $PROJECT_ROOT "setup.log"
$STATE_FILE   = Join-Path $PROJECT_ROOT ".setup_state"
$RAGFLOW_DIR  = Join-Path $PROJECT_ROOT "ragflow_docker"
$EXPORT_DIR   = Join-Path $PROJECT_ROOT "ragflow_export"
$ENV_FILE     = Join-Path $PROJECT_ROOT ".env"
$ENV_EXAMPLE  = Join-Path $PROJECT_ROOT ".env.example"

$RAGFLOW_IMAGE   = "infiniflow/ragflow:v0.24.0"

# GitHub Release 下载配置
$GITHUB_REPO    = "LaFlame111/grain-agent"
$RELEASE_TAG    = "v2.0.0"
$RELEASE_URL    = "https://github.com/$GITHUB_REPO/releases/download/$RELEASE_TAG"
$RELEASE_FILES  = @(
    "images.tar.part-aa",
    "images.tar.part-ab",
    "images.tar.part-ac",
    "vol_mysql.tar.gz",
    "vol_es.tar.gz",
    "vol_minio.tar.gz",
    "vol_redis.tar.gz"
)
$REQUIRED_IMAGES = @("infiniflow/ragflow", "mysql", "elasticsearch", "quay.io/minio/minio", "valkey/valkey")
$TENANT_ID       = "589d787629ea11f18fe89f4b88f5c58b"
$MYSQL_CONTAINER = "ragflow_docker-mysql-1"
$MYSQL_USER      = "root"
$MYSQL_PASS      = "infini_rag_flow"
$MYSQL_DB        = "rag_flow"

$VOLUMES = [ordered]@{
    "ragflow_docker_mysql_data" = "vol_mysql.tar.gz"
    "ragflow_docker_esdata01"   = "vol_es.tar.gz"
    "ragflow_docker_minio_data" = "vol_minio.tar.gz"
    "ragflow_docker_redis_data" = "vol_redis.tar.gz"
}

$SetupStartTime = Get-Date

# ─── 日志系统 ───
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
        default { Write-Host $line }
    }
    $line | Out-File -Append -FilePath $LOG_FILE -Encoding utf8
}

function Run-Logged {
    param([string]$Description, [scriptblock]$Command)
    Log "CMD" ">>> $Description"
    try {
        $output = & $Command 2>&1 | Out-String
        if ($output.Trim()) {
            $output | Out-File -Append -FilePath $LOG_FILE -Encoding utf8
        }
        return $output
    } catch {
        $_.Exception.Message | Out-File -Append -FilePath $LOG_FILE -Encoding utf8
        throw
    }
}

function Step-Header {
    param([int]$Num, [int]$Total, [string]$Title)
    Log "INFO" "--- Step $Num/$Total`: $Title ---"
}

function Elapsed {
    param([datetime]$Start)
    $span = (Get-Date) - $Start
    if ($span.TotalMinutes -ge 1) { return "{0:N0}m{1:N0}s" -f [math]::Floor($span.TotalMinutes), $span.Seconds }
    return "{0:N0}s" -f $span.TotalSeconds
}

# ─── 状态管理 ───
function Get-SetupState {
    if (Test-Path $STATE_FILE) { return (Get-Content $STATE_FILE -Raw).Trim() }
    return ""
}

function Set-SetupState {
    param([string]$State)
    $State | Out-File -FilePath $STATE_FILE -Encoding utf8 -NoNewline
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 0: 管理员自提权
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Host "[提权] 需要管理员权限，正在自动提升..." -ForegroundColor Yellow
    $argList = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process powershell -Verb RunAs -ArgumentList $argList
    exit
}

# ─── 开始 ───
Log "INFO" "========== Grain Agent V010 一键部署 =========="
$osInfo = (Get-CimInstance Win32_OperatingSystem)
$totalMem = [math]::Round($osInfo.TotalVisibleMemorySize / 1MB, 1)
$disk = Get-PSDrive -Name ($PROJECT_ROOT.Substring(0,1))
$diskFree = [math]::Round($disk.Free / 1GB, 1)
Log "INFO" ("系统: {0} {1} | 内存: {2}GB | 磁盘剩余: {3}GB" -f $osInfo.Caption, $osInfo.BuildNumber, $totalMem, $diskFree)
Log "INFO" "项目目录: $PROJECT_ROOT"

$TOTAL_STEPS = 11

# 检查重启恢复
$state = Get-SetupState
if ($state -eq "need_reboot") {
    Log "INFO" "检测到重启恢复状态，从 WSL2 检测继续..."
    Set-SetupState "resumed"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 1: 检测/启用 WSL2
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 1 $TOTAL_STEPS "检测 WSL2"
$stepStart = Get-Date

$wslReady = $false
try {
    $wslOut = wsl --status 2>&1 | Out-String
    if ($wslOut -match "默认版本|Default Version|WSL 2") {
        $wslReady = $true
    }
} catch {}

if (-not $wslReady) {
    # 也尝试 wsl --list 看看
    try {
        $wslList = wsl --list --verbose 2>&1 | Out-String
        if ($wslList -match "WSL 2|VERSION\s+2") { $wslReady = $true }
    } catch {}
}

if ($wslReady) {
    Log "OK" "WSL2 已启用 ($(Elapsed $stepStart))"
} else {
    Log "WARN" "WSL2 未启用，正在启用..."
    try {
        Run-Logged "启用 WSL 功能" {
            dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart 2>&1
        } | Out-Null
        Run-Logged "启用虚拟机平台" {
            dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart 2>&1
        } | Out-Null
    } catch {
        Log "WARN" "DISM 命令返回非零，可能功能已部分启用: $_"
    }

    # 设置 WSL 默认版本
    try { wsl --set-default-version 2 2>&1 | Out-Null } catch {}

    # 检查是否需要重启
    $needReboot = $false
    try {
        $wslCheck = wsl --status 2>&1 | Out-String
        if ($wslCheck -notmatch "默认版本|Default Version|WSL 2") { $needReboot = $true }
    } catch { $needReboot = $true }

    if ($needReboot) {
        Set-SetupState "need_reboot"
        Log "WARN" "WSL2 已启用，需要重启计算机！"
        Log "WARN" "重启后请再次右键运行 setup.ps1，脚本将自动继续。"
        Write-Host ""
        Write-Host "按任意键重启计算机..." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        Restart-Computer -Force
        exit
    }
    Log "OK" "WSL2 已启用 ($(Elapsed $stepStart))"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 2: 检测/安装 Docker Desktop
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 2 $TOTAL_STEPS "检测 Docker Desktop"
$stepStart = Get-Date

function Test-DockerReady {
    try {
        $info = docker info 2>&1 | Out-String
        return ($info -match "Server Version" -or $info -match "Containers")
    } catch { return $false }
}

function Wait-DockerReady {
    param([int]$TimeoutSec = 180)
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        if (Test-DockerReady) { return $true }
        Start-Sleep -Seconds 5
        Write-Host "." -NoNewline
    }
    Write-Host ""
    return $false
}

if (Test-DockerReady) {
    $dockerVer = (docker version --format "{{.Server.Version}}" 2>$null)
    Log "OK" "Docker Desktop 已运行 (v$dockerVer) ($(Elapsed $stepStart))"
} else {
    # 检查是否已安装但未运行
    $dockerExe = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerExe)) {
        $dockerExe = "${env:ProgramFiles}\Docker\Docker Desktop.exe"
    }

    if (Test-Path $dockerExe) {
        Log "INFO" "Docker Desktop 已安装但未运行，正在启动..."
        Start-Process $dockerExe
    } else {
        Log "INFO" "Docker Desktop 未安装，正在下载..."
        $installerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
        $installerPath = Join-Path $env:TEMP "DockerDesktopInstaller.exe"
        try {
            Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
            Log "INFO" "下载完成，正在静默安装（需要几分钟）..."
            $proc = Start-Process -FilePath $installerPath -ArgumentList "install","--quiet","--accept-license" -Wait -PassThru
            if ($proc.ExitCode -ne 0) {
                Log "ERROR" "Docker Desktop 安装失败 (exit code: $($proc.ExitCode))"
                Log "ERROR" "请手动安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
                exit 1
            }
            # 安装后启动
            $dockerExe = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
            if (Test-Path $dockerExe) { Start-Process $dockerExe }
        } catch {
            Log "ERROR" "Docker Desktop 下载/安装失败: $_"
            Log "ERROR" "请手动安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
            exit 1
        }
    }

    Log "INFO" "等待 Docker Desktop 就绪（最长 3 分钟）..."
    if (-not (Wait-DockerReady -TimeoutSec 180)) {
        Log "ERROR" "Docker Desktop 启动超时！请手动启动 Docker Desktop 后重新运行此脚本。"
        exit 1
    }
    $dockerVer = (docker version --format "{{.Server.Version}}" 2>$null)
    Log "OK" "Docker Desktop 已就绪 (v$dockerVer) ($(Elapsed $stepStart))"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 3: WSL2 内存配置
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 3 $TOTAL_STEPS "WSL2 内存配置"
$stepStart = Get-Date

$wslConfigPath = Join-Path $env:USERPROFILE ".wslconfig"
$needWslRestart = $false

if (Test-Path $wslConfigPath) {
    $wslConfig = Get-Content $wslConfigPath -Raw
    if ($wslConfig -match "memory\s*=\s*12GB") {
        Log "OK" "WSL2 内存已配置为 12GB ($(Elapsed $stepStart))"
    } else {
        Log "INFO" "更新 WSL2 内存配置为 12GB..."
        if ($wslConfig -match "memory\s*=") {
            $wslConfig = $wslConfig -replace "memory\s*=\s*\S+", "memory=12GB"
        } elseif ($wslConfig -match "\[wsl2\]") {
            $wslConfig = $wslConfig -replace "(\[wsl2\])", "`$1`nmemory=12GB"
        } else {
            $wslConfig += "`n[wsl2]`nmemory=12GB`n"
        }
        $wslConfig | Out-File -FilePath $wslConfigPath -Encoding utf8 -NoNewline
        $needWslRestart = $true
    }
} else {
    Log "INFO" "创建 .wslconfig 设置 WSL2 内存为 12GB..."
    "[wsl2]`nmemory=12GB`n" | Out-File -FilePath $wslConfigPath -Encoding utf8 -NoNewline
    $needWslRestart = $true
}

if ($needWslRestart) {
    Log "INFO" "重启 WSL 使配置生效..."
    try { wsl --shutdown 2>&1 | Out-Null } catch {}
    Start-Sleep -Seconds 3

    # 等待 Docker 重新就绪
    Log "INFO" "等待 Docker Desktop 重新就绪..."
    if (-not (Wait-DockerReady -TimeoutSec 120)) {
        Log "WARN" "Docker Desktop 未自动恢复，尝试手动启动..."
        $dockerExe = "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe"
        if (Test-Path $dockerExe) { Start-Process $dockerExe }
        if (-not (Wait-DockerReady -TimeoutSec 120)) {
            Log "ERROR" "Docker Desktop 重启失败！请手动启动后重新运行此脚本。"
            exit 1
        }
    }
    Log "OK" "WSL2 内存配置完成 (12GB) ($(Elapsed $stepStart))"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 4: 检测/安装 Python 3.10+
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 4 $TOTAL_STEPS "检测 Python 3.10+"
$stepStart = Get-Date

function Find-Python {
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $ver = & $cmd --version 2>&1 | Out-String
            if ($ver -match "Python\s+(\d+)\.(\d+)") {
                $major = [int]$Matches[1]; $minor = [int]$Matches[2]
                if ($major -ge 3 -and $minor -ge 10) {
                    return @{ Cmd = $cmd; Version = $ver.Trim() }
                }
            }
        } catch {}
    }
    return $null
}

$pyInfo = Find-Python
if ($pyInfo) {
    Log "OK" "$($pyInfo.Version) 已安装 ($(Elapsed $stepStart))"
    $PYTHON = $pyInfo.Cmd
} else {
    Log "INFO" "Python 3.10+ 未找到，正在下载 Python 3.12..."
    $pyUrl = "https://www.python.org/ftp/python/3.12.7/python-3.12.7-amd64.exe"
    $pyInstaller = Join-Path $env:TEMP "python-3.12.7-amd64.exe"
    try {
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
        Log "INFO" "下载完成，正在静默安装..."
        $proc = Start-Process -FilePath $pyInstaller -ArgumentList `
            "/quiet","InstallAllUsers=1","PrependPath=1","Include_test=0" -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            Log "ERROR" "Python 安装失败 (exit code: $($proc.ExitCode))"
            Log "ERROR" "请手动安装 Python 3.10+: https://www.python.org/downloads/"
            exit 1
        }
        # 刷新 PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                     [System.Environment]::GetEnvironmentVariable("Path", "User")
        Start-Sleep -Seconds 2
        $pyInfo = Find-Python
        if (-not $pyInfo) {
            Log "ERROR" "Python 安装后仍无法找到。请重新打开终端或手动安装。"
            exit 1
        }
        $PYTHON = $pyInfo.Cmd
        Log "OK" "$($pyInfo.Version) 安装完成 ($(Elapsed $stepStart))"
    } catch {
        Log "ERROR" "Python 下载/安装失败: $_"
        Log "ERROR" "请手动安装 Python 3.10+: https://www.python.org/downloads/"
        exit 1
    }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 5: 下载 RAGFlow 镜像和数据（从 GitHub Releases）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 5 $TOTAL_STEPS "下载 RAGFlow 镜像和数据"
$stepStart = Get-Date

if (-not (Test-Path $EXPORT_DIR)) {
    New-Item -ItemType Directory -Path $EXPORT_DIR -Force | Out-Null
}

$needDownload = $false
foreach ($f in $RELEASE_FILES) {
    if (-not (Test-Path (Join-Path $EXPORT_DIR $f))) {
        $needDownload = $true
        break
    }
}

if ($needDownload) {
    Log "INFO" "从 GitHub Releases ($RELEASE_TAG) 下载文件..."
    $maxRetries = 3

    foreach ($f in $RELEASE_FILES) {
        $dest = Join-Path $EXPORT_DIR $f
        if (Test-Path $dest) {
            Log "OK" "$f 已存在，跳过"
            continue
        }

        $url = "$RELEASE_URL/$f"
        $downloaded = $false

        for ($attempt = 1; $attempt -le $maxRetries; $attempt++) {
            Log "INFO" "下载 $f（第 ${attempt}/${maxRetries} 次）..."
            try {
                # 使用 curl.exe（Windows 自带）支持断点续传和进度条
                $curlArgs = @("-L", "-C", "-", "--retry", "3", "--retry-delay", "5", "--progress-bar", "-o", $dest, $url)
                Log "CMD" ">>> curl.exe $($curlArgs -join ' ')"
                $proc = Start-Process -FilePath "curl.exe" -ArgumentList $curlArgs -Wait -PassThru -NoNewWindow
                if ($proc.ExitCode -eq 0 -and (Test-Path $dest)) {
                    $sizeMB = [math]::Round((Get-Item $dest).Length / 1MB, 1)
                    Log "OK" "$f 下载完成 (${sizeMB}MB)"
                    $downloaded = $true
                    break
                }
                Log "WARN" "下载返回 exit code: $($proc.ExitCode)"
            } catch {
                Log "WARN" "下载失败: $_"
            }
            if ($attempt -lt $maxRetries) {
                Log "INFO" "5 秒后重试..."
                Start-Sleep -Seconds 5
            }
        }

        if (-not $downloaded) {
            Log "ERROR" "文件 $f 下载失败（已重试 $maxRetries 次）"
            Log "ERROR" "请检查网络连接，或手动下载: $url"
            exit 1
        }
    }
    Log "OK" "所有文件下载完成 ($(Elapsed $stepStart))"
} else {
    Log "OK" "ragflow_export/ 文件已齐全，跳过下载 ($(Elapsed $stepStart))"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 6: 导入 Docker 镜像
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 6 $TOTAL_STEPS "导入 Docker 镜像"
$stepStart = Get-Date

# 检查是否已导入
$existingImages = docker images --format "{{.Repository}}" 2>$null | Out-String
$allPresent = $true
foreach ($img in $REQUIRED_IMAGES) {
    if ($existingImages -notmatch [regex]::Escape($img)) {
        $allPresent = $false
        break
    }
}

if ($allPresent) {
    Log "OK" "所有镜像已存在，跳过导入 ($(Elapsed $stepStart))"
} else {
    $imagesTar = Join-Path $EXPORT_DIR "images.tar"

    # 如果 images.tar 不存在但分卷存在，先合并
    if (-not (Test-Path $imagesTar)) {
        $parts = Get-ChildItem -Path $EXPORT_DIR -Filter "images.tar.part-*" | Sort-Object Name
        if ($parts.Count -gt 0) {
            Log "INFO" "合并分卷文件 ($($parts.Count) 个分卷)..."
            $outStream = [System.IO.File]::Create($imagesTar)
            try {
                foreach ($part in $parts) {
                    Log "CMD" "  合并: $($part.Name)"
                    $inStream = [System.IO.File]::OpenRead($part.FullName)
                    $inStream.CopyTo($outStream)
                    $inStream.Close()
                }
            } finally {
                $outStream.Close()
            }
            $sizeMB = [math]::Round((Get-Item $imagesTar).Length / 1MB, 0)
            Log "OK" "分卷合并完成 (${sizeMB}MB)"
        } else {
            Log "ERROR" "找不到 ragflow_export/images.tar 或分卷文件！"
            exit 1
        }
    }

    Log "INFO" "正在导入镜像（可能需要几分钟）..."
    $loadOutput = Run-Logged "docker load -i $imagesTar" {
        docker load -i $imagesTar 2>&1
    }
    Log "CMD" $loadOutput.Trim()

    # 验证
    $existingImages = docker images --format "{{.Repository}}:{{.Tag}}" 2>$null | Out-String
    $verified = 0
    foreach ($img in $REQUIRED_IMAGES) {
        if ($existingImages -match [regex]::Escape($img)) {
            $verified++
        } else {
            Log "WARN" "镜像未找到: $img"
        }
    }
    Log "OK" "镜像导入完成 ($verified/$($REQUIRED_IMAGES.Count) 镜像验证通过) ($(Elapsed $stepStart))"
    if ($verified -lt $REQUIRED_IMAGES.Count) {
        Log "WARN" "部分镜像缺失，部署可能出问题"
    }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 7: 首次启动 RAGFlow（创建数据卷）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 7 $TOTAL_STEPS "首次启动 RAGFlow（创建数据卷）"
$stepStart = Get-Date

# 检查数据卷是否已有数据（如果已有则跳过 Step 7+8）
$volumeExists = $false
try {
    $volList = docker volume ls --format "{{.Name}}" 2>$null | Out-String
    $allVolumesExist = $true
    foreach ($vol in $VOLUMES.Keys) {
        if ($volList -notmatch [regex]::Escape($vol)) {
            $allVolumesExist = $false
            break
        }
    }
    $volumeExists = $allVolumesExist
} catch {}

if ($volumeExists) {
    Log "OK" "数据卷已存在，跳过首次启动 ($(Elapsed $stepStart))"
} else {
    $prevDir = Get-Location
    Set-Location $RAGFLOW_DIR
    try {
        Log "INFO" "启动 Docker Compose 以创建数据卷..."
        $composeUp = Run-Logged "docker compose up -d" {
            docker compose up -d 2>&1
        }
        Log "CMD" $composeUp.Trim()

        # 等待 MySQL healthy
        Log "INFO" "等待 MySQL 容器就绪（最长 2 分钟）..."
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $mysqlReady = $false
        while ($sw.Elapsed.TotalSeconds -lt 120) {
            $ps = docker compose ps --format "{{.Name}} {{.Status}}" 2>$null | Out-String
            if ($ps -match "mysql.*healthy") {
                $mysqlReady = $true
                break
            }
            Start-Sleep -Seconds 5
            Write-Host "." -NoNewline
        }
        Write-Host ""

        if ($mysqlReady) {
            Log "OK" "MySQL 容器就绪"
        } else {
            Log "WARN" "MySQL 容器未报告 healthy，继续尝试..."
        }

        Log "INFO" "停止容器（保留数据卷）..."
        $composeDown = Run-Logged "docker compose down" {
            docker compose down 2>&1
        }
        Log "CMD" $composeDown.Trim()
        Log "OK" "数据卷已创建 ($(Elapsed $stepStart))"
    } finally {
        Set-Location $prevDir
    }
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 8: 导入数据卷
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 8 $TOTAL_STEPS "导入数据卷（知识库数据）"
$stepStart = Get-Date

# 检查 MySQL 数据卷是否已有数据（简单判断：卷内文件数 > 10 表示已导入）
$skipImport = $false
try {
    $checkOutput = docker run --rm -v "ragflow_docker_mysql_data:/data:ro" $RAGFLOW_IMAGE sh -c "ls /data/ 2>/dev/null | wc -l" 2>$null
    if ([int]$checkOutput.Trim() -gt 5) {
        $skipImport = $true
    }
} catch {}

if ($skipImport) {
    Log "OK" "数据卷已有数据，跳过导入 ($(Elapsed $stepStart))"
} else {
    $exportPath = (Resolve-Path $EXPORT_DIR).Path

    foreach ($entry in $VOLUMES.GetEnumerator()) {
        $volName = $entry.Key
        $tarFile = $entry.Value
        $tarPath = Join-Path $EXPORT_DIR $tarFile

        if (-not (Test-Path $tarPath)) {
            Log "WARN" "跳过 $volName`: 文件 $tarFile 不存在"
            continue
        }

        Log "INFO" "导入 $volName <- $tarFile ..."
        $importOutput = Run-Logged "docker run --rm -v ${volName}:/data -v ${exportPath}:/backup:ro $RAGFLOW_IMAGE tar xzf /backup/$tarFile -C /data" {
            docker run --rm `
                -v "${volName}:/data" `
                -v "${exportPath}:/backup:ro" `
                $RAGFLOW_IMAGE sh -c "cd /data && tar xzf /backup/$tarFile"
        }
        if ($importOutput.Trim()) { Log "CMD" $importOutput.Trim() }
    }
    Log "OK" "数据卷导入完成 ($(Elapsed $stepStart))"
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 9: 启动 RAGFlow（带数据）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 9 $TOTAL_STEPS "启动 RAGFlow（带数据）"
$stepStart = Get-Date

$prevDir = Get-Location
Set-Location $RAGFLOW_DIR
try {
    $composeUp = Run-Logged "docker compose up -d" {
        docker compose up -d 2>&1
    }
    Log "CMD" $composeUp.Trim()

    # 等待所有容器 healthy
    Log "INFO" "等待所有容器就绪（最长 3 分钟）..."
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $allHealthy = $false
    while ($sw.Elapsed.TotalSeconds -lt 180) {
        $ps = docker compose ps --format "{{.Name}} {{.Status}}" 2>$null | Out-String
        $unhealthy = $ps -split "`n" | Where-Object { $_ -match "\S" -and $_ -notmatch "healthy|running" -and $_ -notmatch "^\s*$" }
        if (-not $unhealthy -or $unhealthy.Count -eq 0) {
            # 额外检查：至少有容器在运行
            $running = $ps -split "`n" | Where-Object { $_ -match "running|healthy" }
            if ($running.Count -ge 3) {
                $allHealthy = $true
                break
            }
        }
        Start-Sleep -Seconds 5
        Write-Host "." -NoNewline
    }
    Write-Host ""

    if ($allHealthy) {
        Log "OK" "所有容器已就绪"
    } else {
        Log "WARN" "部分容器可能未完全就绪，继续..."
        $psOutput = docker compose ps 2>$null | Out-String
        Log "CMD" $psOutput
    }

    # 验证 RAGFlow API 可达
    Log "INFO" "验证 RAGFlow API..."
    $ragflowReady = $false
    $sw2 = [Diagnostics.Stopwatch]::StartNew()
    while ($sw2.Elapsed.TotalSeconds -lt 60) {
        try {
            $resp = Invoke-WebRequest -Uri "http://localhost:9380" -UseBasicParsing -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($resp.StatusCode -lt 500) {
                $ragflowReady = $true
                break
            }
        } catch {}
        Start-Sleep -Seconds 5
    }

    if ($ragflowReady) {
        Log "OK" "RAGFlow API 可达 (http://localhost:9380) ($(Elapsed $stepStart))"
    } else {
        Log "WARN" "RAGFlow API 暂时不可达，可能需要更长启动时间"
    }
} finally {
    Set-Location $prevDir
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 10: Python 依赖 + .env 配置
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 10 $TOTAL_STEPS "安装 Python 依赖 + 配置 .env"
$stepStart = Get-Date

# 安装 Python 依赖
Log "INFO" "安装 Python 依赖..."
$pipOutput = Run-Logged "$PYTHON -m pip install -r requirements.txt -q" {
    & $PYTHON -m pip install -r (Join-Path $PROJECT_ROOT "requirements.txt") -q 2>&1
}
if ($pipOutput.Trim()) { Log "CMD" $pipOutput.Trim() }
Log "OK" "Python 依赖安装完成"

# .env 配置
if (-not (Test-Path $ENV_FILE)) {
    Log "INFO" "创建 .env 配置文件..."
    Copy-Item $ENV_EXAMPLE $ENV_FILE
}

# 读取当前 .env
$envContent = Get-Content $ENV_FILE -Raw

# 交互式获取 DASHSCOPE_API_KEY
$currentKey = ""
if ($envContent -match "DASHSCOPE_API_KEY=(.+)") {
    $currentKey = $Matches[1].Trim()
}

if ($currentKey -eq "" -or $currentKey -eq "你的通义千问API_Key") {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Cyan
    Write-Host " 请输入通义千问 API Key (DASHSCOPE_API_KEY)" -ForegroundColor Cyan
    Write-Host " 申请地址: https://dashscope.console.aliyun.com/" -ForegroundColor Cyan
    Write-Host "============================================" -ForegroundColor Cyan
    $apiKey = Read-Host "DASHSCOPE_API_KEY"
    if ($apiKey) {
        $envContent = $envContent -replace "DASHSCOPE_API_KEY=.+", "DASHSCOPE_API_KEY=$apiKey"
        $envContent | Out-File -FilePath $ENV_FILE -Encoding utf8 -NoNewline
        Log "OK" "DASHSCOPE_API_KEY 已写入"
    } else {
        Log "WARN" "未输入 API Key，请稍后手动编辑 .env 文件"
    }
} else {
    Log "OK" "DASHSCOPE_API_KEY 已配置"
}

# 自动获取 RAGFlow API Key 和数据集 ID
Log "INFO" "自动配置 RAGFlow API Key 和数据集 ID..."

# 等待 MySQL 容器可用
$mysqlOk = $false
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 30) {
    try {
        $ping = docker exec $MYSQL_CONTAINER mysqladmin -u$MYSQL_USER -p$MYSQL_PASS ping 2>$null | Out-String
        if ($ping -match "alive") { $mysqlOk = $true; break }
    } catch {}
    Start-Sleep -Seconds 3
}

if ($mysqlOk) {
    # 生成 API Token
    $tokenUuid = [guid]::NewGuid().ToString("N")
    $apiToken = "ragflow-$tokenUuid"
    $nowMs = [long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
    $nowDt = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

    $sql = "INSERT INTO api_token (create_time, create_date, update_time, update_date, tenant_id, token, source) VALUES ($nowMs, '$nowDt', $nowMs, '$nowDt', '$TENANT_ID', '$apiToken', 'markdown');"

    Log "CMD" "创建 RAGFlow API Token..."
    $insertResult = docker exec $MYSQL_CONTAINER mysql -u$MYSQL_USER -p$MYSQL_PASS $MYSQL_DB -e "$sql" 2>&1 | Out-String
    $insertResult | Out-File -Append -FilePath $LOG_FILE -Encoding utf8

    if ($LASTEXITCODE -eq 0 -or $insertResult -notmatch "ERROR") {
        Log "OK" "RAGFlow API Token 已创建"

        # 写入 .env
        $envContent = Get-Content $ENV_FILE -Raw
        $envContent = $envContent -replace "RAGFLOW_API_KEY=.+", "RAGFLOW_API_KEY=$apiToken"
        $envContent | Out-File -FilePath $ENV_FILE -Encoding utf8 -NoNewline

        # 获取数据集 ID
        Start-Sleep -Seconds 2
        try {
            $dsResp = Invoke-RestMethod -Uri "http://localhost:9380/api/v1/datasets?page=1&page_size=30" `
                -Headers @{ "Authorization" = "Bearer $apiToken" } -TimeoutSec 10
            if ($dsResp.code -eq 0 -and $dsResp.data) {
                $datasetIds = ($dsResp.data | ForEach-Object { $_.id }) -join ","
                if ($datasetIds) {
                    $envContent = Get-Content $ENV_FILE -Raw
                    $envContent = $envContent -replace "RAGFLOW_DATASET_IDS=.+", "RAGFLOW_DATASET_IDS=$datasetIds"
                    $envContent | Out-File -FilePath $ENV_FILE -Encoding utf8 -NoNewline
                    Log "OK" "数据集 ID 已写入: $datasetIds"
                    foreach ($ds in $dsResp.data) {
                        Log "INFO" ("  数据集: {0} (ID: {1}, 文档数: {2})" -f $ds.name, $ds.id, $ds.doc_num)
                    }
                } else {
                    Log "WARN" "未找到数据集，请稍后手动配置 RAGFLOW_DATASET_IDS"
                }
            } else {
                Log "WARN" "数据集查询返回异常: $($dsResp | ConvertTo-Json -Compress)"
            }
        } catch {
            Log "WARN" "数据集查询失败: $_ — RAGFlow 可能需要更长启动时间，请稍后运行:"
            Log "WARN" "  python setup_apitoken.py"
        }
    } else {
        Log "WARN" "Token 写入失败，请稍后手动运行: python setup_apitoken.py"
        Log "CMD" $insertResult.Trim()
    }
} else {
    Log "WARN" "MySQL 容器不可用，跳过自动配置。请稍后手动运行: python setup_apitoken.py"
}

Log "OK" "配置完成 ($(Elapsed $stepStart))"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Step 11: 输出总结
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Step-Header 11 $TOTAL_STEPS "完成"

# 清理状态文件
if (Test-Path $STATE_FILE) { Remove-Item $STATE_FILE -Force }

$totalElapsed = Elapsed $SetupStartTime

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " Grain Agent V010 — 部署完成！" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host " RAGFlow Web UI:  http://localhost:80" -ForegroundColor Cyan
Write-Host " RAGFlow API:     http://localhost:9380" -ForegroundColor Cyan
Write-Host ""
Write-Host " 启动 Agent:" -ForegroundColor White
Write-Host "   .\start_server.ps1         (PowerShell)" -ForegroundColor White
Write-Host "   bash start.sh              (Git Bash)" -ForegroundColor DarkGray
Write-Host ""
Write-Host " 停止 Agent:" -ForegroundColor White
Write-Host "   .\stop_server.ps1          (PowerShell)" -ForegroundColor White
Write-Host "   bash stop.sh               (Git Bash)" -ForegroundColor DarkGray
Write-Host ""
Write-Host " 前端: http://127.0.0.1:8000/ui (Agent 启动后)" -ForegroundColor Cyan
Write-Host ""
Write-Host " 日志: $LOG_FILE" -ForegroundColor DarkGray
Write-Host " 总耗时: $totalElapsed" -ForegroundColor DarkGray
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

Log "OK" "========== 部署完成 (总耗时 $totalElapsed) =========="

Write-Host "按任意键退出..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
