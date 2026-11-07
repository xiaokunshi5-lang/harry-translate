@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo    Harry Translate (哈利同传) 国际会议实时双语同传系统
echo ==========================================================

REM 检查并自动初始化 .env 配置文件 (零门槛克隆自举)
if not exist ".env" (
    if exist ".env.example" (
        echo [配置] 未检测到 .env，正在基于 .env.example 自动生成初始配置...
        copy /Y ".env.example" ".env" >nul
        echo [提示] 首次使用请在打开的网页主控台设置中填入阿里云百炼 API Key。
    ) else (
        echo [错误] 未检测到 .env 及 .env.example 配置文件！
        pause
        exit /b 1
    )
)

REM 智能检测与自动初始化 .venv 虚拟环境
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    echo [初始化] 首次运行：正在为您自动创建 .venv 虚拟环境并安装依赖...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if exist ".venv\Scripts\python.exe" (
        ".venv\Scripts\python.exe" -m pip install -r requirements.txt
        set "PYTHON_CMD=.venv\Scripts\python.exe"
    ) else (
        set "PYTHON_CMD=python"
    )
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
