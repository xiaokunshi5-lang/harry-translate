@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo    Harry Translate (哈利同传) 国际会议实时双语同传系统
echo ==========================================================

REM 检查 .env 配置文件
if not exist ".env" (
    echo [错误] 未检测到 .env 配置文件，请先创建并配置 DASHSCOPE_API_KEY。
    pause
    exit /b 1
)

REM 激活虚拟环境或定位 Python 解释器
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    set "PYTHON_CMD=python"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

echo 正在启动双通道同传服务...
echo   • 主控面板:    http://localhost:8000/
echo   • 中译英大屏:  http://localhost:8000/en   (面向外宾)
echo   • 英译中大屏:  http://localhost:8000/zh   (面向中方)
echo   • 左右双栏屏:  http://localhost:8000/split (现场监看)
echo ----------------------------------------------------------

REM 自动在默认浏览器打开双栏大屏与主控
start "" "http://localhost:8000/split"

REM 启动同传服务端
"%PYTHON_CMD%" server.py
pause
