# Grain Agent V008 - 智能启动脚本
# 功能：启动前自动清理残留进程，启动后记录 PID，支持优雅关闭

param(
    [int]$Port = 8000,
    [string]$HostAddress = "0.0.0.0",
    [switch]$Debug = $false
)

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Grain Agent V008 - 服务启动脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 检查并清理残留进程
Write-Host "[1/4] 检查端口占用..." -ForegroundColor Yellow
$portProcesses = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
    Where-Object { $_.State -eq "Listen" } | 
    Select-Object -ExpandProperty OwningProcess -Unique

if ($portProcesses) {
    Write-Host "  发现端口 $Port 被占用，正在清理..." -ForegroundColor Yellow
    foreach ($processId in $portProcesses) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "  终止进程: $($process.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 1
}

# 2. 清理 uvicorn 进程
Write-Host "[2/4] 清理 uvicorn 进程..." -ForegroundColor Yellow
Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | 
    Where-Object { $_.Path -like "*python*" } | 
    ForEach-Object {
        Write-Host "  终止进程: uvicorn (PID: $($_.Id))" -ForegroundColor Yellow
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }

# 3. 检查环境变量
Write-Host "[3/4] 检查环境配置..." -ForegroundColor Yellow
if (-not $env:DASHSCOPE_API_KEY) {
    Write-Host "  ⚠️  警告: DASHSCOPE_API_KEY 未设置!" -ForegroundColor Red
    Write-Host "  请设置环境变量或创建 .env 文件" -ForegroundColor Red
}

# 4. 启动服务
Write-Host "[4/4] 启动服务..." -ForegroundColor Yellow
Write-Host "  端口: $Port" -ForegroundColor Green
Write-Host "  主机: $HostAddress" -ForegroundColor Green
Write-Host "  调试模式: $Debug" -ForegroundColor Green
Write-Host ""

# 设置调试环境变量
if ($Debug) {
    $env:DEBUG = "true"
    $env:EXPOSE_DOCS = "true"
}

# PID 文件路径
$pidFile = Join-Path $PSScriptRoot ".server.pid"
$logFile = Join-Path $PSScriptRoot "server.log"

# 启动 uvicorn
Write-Host "正在启动服务..." -ForegroundColor Green
Write-Host "按 Ctrl+C 优雅停止服务" -ForegroundColor Cyan
Write-Host ""

try {
    # 使用 Start-Process 启动，记录 PID
    # 注意：RedirectStandardOutput 和 RedirectStandardError 必须不同
    $errorLogFile = Join-Path $PSScriptRoot "server_error.log"
    $process = Start-Process -FilePath "python" `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", $HostAddress, "--port", $Port, "--reload" `
        -PassThru -NoNewWindow `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError $errorLogFile
    
    # 保存 PID
    $process.Id | Out-File -FilePath $pidFile -Encoding utf8
    Write-Host "✅ 服务已启动 (PID: $($process.Id))" -ForegroundColor Green
    Write-Host "📝 日志文件: $logFile" -ForegroundColor Cyan
    Write-Host "🆔 PID 文件: $pidFile" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "服务地址: http://$HostAddress`:$Port" -ForegroundColor Green
    if ($Debug) {
        Write-Host "API 文档: http://localhost:$Port/docs" -ForegroundColor Green
    }
    Write-Host ""
    
    # 等待进程结束
    $process.WaitForExit()
    
} catch {
    Write-Host "❌ 启动失败: $_" -ForegroundColor Red
    exit 1
} finally {
    # 清理 PID 文件
    if (Test-Path $pidFile) {
        Remove-Item $pidFile -Force
    }
    Write-Host ""
    Write-Host "服务已停止" -ForegroundColor Yellow
}
