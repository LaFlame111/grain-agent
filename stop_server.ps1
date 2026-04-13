# Grain Agent - 停止脚本 (Windows PowerShell)
# 用法: .\stop_server.ps1
# 不依赖 PID 文件，直接按端口和进程名查找并终止

param(
    [int]$Port = 8000
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$ErrorActionPreference = "Continue"   # 不因单步失败而中断

Write-Host "==============================" -ForegroundColor Cyan
Write-Host " Grain Agent 停止" -ForegroundColor Cyan
Write-Host "==============================" -ForegroundColor Cyan

$killed = $false

# 1. 按端口找进程并杀掉（含父进程 nohup/bash）
Write-Host "[1/2] 查找占用端口 $Port 的进程..." -ForegroundColor Yellow
$conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($conns) {
    $pids = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  终止: $($proc.Name) (PID $procId)" -ForegroundColor Yellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            $killed = $true

            # 同时尝试杀父进程（处理 nohup/bash 层）
            $parentId = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue).ParentProcessId
            if ($parentId -and $parentId -gt 4) {
                $parent = Get-Process -Id $parentId -ErrorAction SilentlyContinue
                if ($parent -and $parent.Name -notmatch "^(svchost|explorer|winlogon|csrss|lsass|services|wininit|System)$") {
                    Write-Host "  终止父进程: $($parent.Name) (PID $parentId)" -ForegroundColor Yellow
                    Stop-Process -Id $parentId -Force -ErrorAction SilentlyContinue
                }
            }
        }
    }
} else {
    Write-Host "  端口 $Port 未被占用" -ForegroundColor Green
}

Start-Sleep -Milliseconds 800

# 2. 验证
Write-Host "[2/2] 验证端口释放..." -ForegroundColor Yellow
$remaining = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host "  警告：端口 $Port 仍被占用，请手动处理" -ForegroundColor Red
} else {
    Write-Host "  端口 $Port 已释放" -ForegroundColor Green
}

# 清理 PID 文件（兼容 start.sh 和 start_server.ps1 两种格式）
$pidFile = Join-Path $PSScriptRoot ".server.pid"
if (Test-Path $pidFile) {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    Write-Host "  PID 文件已清理" -ForegroundColor Green
}

Write-Host ""
if ($killed) {
    Write-Host "服务器已停止" -ForegroundColor Green
} else {
    Write-Host "服务器本来就没在运行" -ForegroundColor Green
}
