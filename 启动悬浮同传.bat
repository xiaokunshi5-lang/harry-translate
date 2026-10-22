@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo    Harry Translate (哈利同传) 极简桌面悬浮同传 HUD
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
    echo [提示] 未检测到 .venv 虚拟环境，使用系统 python...
    set "PYTHON_CMD=python"
)

REM 检查 8000 端口并按需后台启动 server.py
netstat -ano | findstr :8000 >nul
if errorlevel 1 (
    echo [服务] 正在后台启动同传服务端 (端口 8000)...
    start /b "" "%PYTHON_CMD%" server.py
    timeout /t 2 /nobreak >nul
) else (
    echo [服务] 检测到同传服务已在运行 (端口 8000)。
)

REM [防重] 终止历史残留的 float_app.py 孤儿进程
wmic process where "commandline like '%%float_app.py%%' and name like '%%python%%'" call terminate >nul 2>&1

echo [HUD] 正在启动桌面悬浮 HUD...
"%PYTHON_CMD%" float_app.py
if errorlevel 1 (
    echo [提示] 原生悬浮窗口启动异常或不可用，正在启动网页版悬浮窗作为零门槛兜底...
    start http://localhost:8000/hud
    echo 网页版悬浮窗已在浏览器中打开：http://localhost:8000/hud
    pause
)

exit /b 0
