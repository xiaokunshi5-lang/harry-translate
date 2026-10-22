@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================================
echo    DashScope API Key 快速切换与验证工具
echo ==========================================================

REM 激活虚拟环境或定位 Python 解释器
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    set "PYTHON_CMD=python"
) else if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
    set "PYTHON_CMD=python"
)

"%PYTHON_CMD%" switch_key.py %*

echo.
echo ----------------------------------------------------------
pause
