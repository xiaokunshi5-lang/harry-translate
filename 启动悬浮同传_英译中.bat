@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo    会议实时桌面悬浮同传 HUD · 英译中专属通道 (ZH)
echo    适用场景: 外教课、跨国讲座、听取英文汇报 (节省50%% Token)
echo ==========================================================

REM 检查并自动初始化 .env 配置文件 (零门槛克隆自举)
if not exist ".env" (
    if exist ".env.example" (
        echo [配置] 未检测到 .env，正在基于 .env.example 自动生成初始配置...
        copy /Y ".env.example" ".env" >nul
        echo [提示] 首次使用请在启动后点击悬浮窗 ⚙️ 或打开 http://localhost:8000 填入阿里云百炼 API Key。
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
        echo [提示] 自动创建 .venv 失败，回退使用系统 python...
        set "PYTHON_CMD=python"
    )
)

REM 检查 8000 端口并按需后台启动 server.py (注意括号块内使用 ^( ^) 转义)
netstat -ano | findstr :8000 >nul
if errorlevel 1 (
    echo [服务] 正在后台启动同传服务端 ^(端口 8000^)...
    start /b "" "%PYTHON_CMD%" server.py
    timeout /t 2 /nobreak >nul
) else (
    echo [服务] 检测到同传服务已在运行 ^(端口 8000^)。
)

REM [防重] 终止历史残留的 float_app.py 孤儿进程 (优先极速 wmic，Win11 24H2 自动回退 PowerShell)
where wmic >nul 2>&1 && (
    wmic process where "commandline like '%%float_app.py%%' and name like '%%python%%'" call terminate >nul 2>&1
) || (
    powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*float_app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
)

echo [HUD] 正在启动英译中专属悬浮 HUD...
"%PYTHON_CMD%" float_app.py --channel zh
if errorlevel 1 (
    echo [提示] 原生悬浮窗口启动异常或不可用，正在启动网页版悬浮窗作为零门槛兜底...
    start http://localhost:8000/hud?channel=zh
    echo 网页版悬浮窗已在浏览器中打开：http://localhost:8000/hud?channel=zh
    pause
)

exit /b 0
