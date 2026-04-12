@echo off
chcp 65001 >nul
echo ============================================================
echo Grain Agent V006 - 进程清理脚本（备用工具）
echo ============================================================
echo.
echo 注意：推荐使用 stop_server.ps1 进行优雅停止
echo 此脚本用于紧急清理或 stop_server.ps1 失败时使用
echo.

REM 尝试使用 PowerShell 脚本（如果可用）
powershell -ExecutionPolicy Bypass -File "%~dp0stop_server.ps1" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ 已使用 PowerShell 脚本完成清理
    pause
    exit /b 0
)

echo PowerShell 脚本不可用，使用备用清理方法...
echo.

echo 1. 尝试停止占用 8000 端口的进程...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo 发现端口 8000 被 PID %%a 占用，正在强制结束...
    taskkill /F /PID %%a /T
)

echo 2. 强制结束所有 uvicorn 进程...
taskkill /F /IM uvicorn.exe /T 2>nul

echo 3. 清理 PID 文件...
if exist "%~dp0.server.pid" del /F /Q "%~dp0.server.pid"

echo ============================================================
echo 清理完成！现在可以重新启动服务了。
echo ============================================================
echo.
echo 提示：下次请使用 stop_server.ps1 进行优雅停止
pause
