# Grain Agent V008 - 优雅停止脚本
# 功能：优雅地停止服务，先尝试 SIGTERM，失败后再强制终止

param(
    [int]$Port = 8000
)

# 设置控制台编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Grain Agent V008 - 服务停止脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. 从 PID 文件读取进程 ID
$pidFile = Join-Path $PSScriptRoot ".server.pid"
if (Test-Path $pidFile) {
    $processId = Get-Content $pidFile -Raw | ForEach-Object { $_.Trim() }
    Write-Host "[1/3] 从 PID 文件读取进程 ID: $processId" -ForegroundColor Yellow
    
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        Write-Host "  发现进程: $($process.ProcessName) (PID: $processId)" -ForegroundColor Yellow
        Write-Host "  正在优雅停止..." -ForegroundColor Yellow
        
        # 尝试优雅停止（发送 Ctrl+C 信号）
        try {
            # Windows 上使用 taskkill /PID <pid> 发送终止信号
            $result = taskkill /PID $processId /T 2>&1
            Start-Sleep -Seconds 2
            
            # 检查进程是否还在运行
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if (-not $process) {
                Write-Host "  ✅ 进程已优雅停止" -ForegroundColor Green
            } else {
                Write-Host "  ⚠️  进程仍在运行，强制终止..." -ForegroundColor Yellow
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                Write-Host "  ✅ 进程已强制终止" -ForegroundColor Green
            }
        } catch {
            Write-Host "  ⚠️  停止失败，尝试强制终止..." -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
        
        # 清理 PID 文件
        Remove-Item $pidFile -Force
    } else {
        Write-Host "  ⚠️  PID 文件中的进程不存在，清理 PID 文件" -ForegroundColor Yellow
        Remove-Item $pidFile -Force
    }
}

# 2. 检查端口占用
Write-Host "[2/3] 检查端口 $Port 占用..." -ForegroundColor Yellow
$portProcesses = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | 
    Where-Object { $_.State -eq "Listen" } | 
    Select-Object -ExpandProperty OwningProcess -Unique

if ($portProcesses) {
    foreach ($processId in $portProcesses) {
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -eq "python") {
            Write-Host "  发现占用端口的进程: $($process.ProcessName) (PID: $processId)" -ForegroundColor Yellow
            Write-Host "  正在停止..." -ForegroundColor Yellow
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Write-Host "  ✅ 进程已停止" -ForegroundColor Green
        }
    }
} else {
    Write-Host "  ✅ 端口 $Port 未被占用" -ForegroundColor Green
}

# 3. 清理 uvicorn 进程
Write-Host "[3/3] 清理 uvicorn 进程..." -ForegroundColor Yellow
$uvicornProcesses = Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue
if ($uvicornProcesses) {
    foreach ($proc in $uvicornProcesses) {
        Write-Host "  终止进程: uvicorn (PID: $($proc.Id))" -ForegroundColor Yellow
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "  ✅ uvicorn 进程已清理" -ForegroundColor Green
} else {
    Write-Host "  ✅ 无 uvicorn 进程运行" -ForegroundColor Green
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "✅ 服务已停止" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
