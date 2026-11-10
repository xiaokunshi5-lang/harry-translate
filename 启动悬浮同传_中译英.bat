@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
if not exist ".venv\Scripts\python.exe" (
    echo Project Python environment is missing.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" windows_launcher.py --channel en
if errorlevel 1 pause
