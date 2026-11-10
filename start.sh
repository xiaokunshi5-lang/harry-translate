#!/bin/bash

# 获取当前脚本所在目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "=========================================================="
echo "    Harry Translate (哈利同传) 国际会议实时双语同传系统    "
echo "=========================================================="

# 智能检测与激活 Python 运行环境 (本地 .venv 优先，自动初始化/系统环境兜底)
PYTHON=""
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    if python3 -c "import fastapi, uvicorn, pywebview, pyaudio" >/dev/null 2>&1; then
        echo ">> [提示] 未发现 .venv，但系统 Python3 依赖完备，使用系统 Python3..."
        PYTHON="python3"
    else
        echo ">> [初始化] 未检测到 .venv 虚拟环境，正在为您自动创建并安装依赖..."
        python3 -m venv .venv
        if [ -f ".venv/bin/python" ]; then
            .venv/bin/pip install -r requirements.txt
            PYTHON=".venv/bin/python"
            echo ">> [就绪] 虚拟环境已成功初始化！"
        else
            echo ">> [错误] 自动创建 .venv 失败，请检查 Python3 环境。"
            exit 1
        fi
    fi
else
    echo ">> [错误] 未检测到 Python3 运行环境，请先安装 Python 3.10+。"
    exit 1
fi

# 检查并自动同步 .env 配置文件
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo ">> [配置] 正在基于 .env.example 自动生成 .env 初始配置..."
        cp ".env.example" ".env"
    fi
fi

echo ">> 正在启动双通道同传服务..."
echo "   • 主控面板:    http://localhost:8000/"
echo "   • 中译英大屏:  http://localhost:8000/en   (面向外宾)"
echo "   • 英译中大屏:  http://localhost:8000/zh   (面向中方)"
echo "   • 左右双栏屏:  http://localhost:8000/split (现场监看)"
echo "----------------------------------------------------------"

# 自动在默认浏览器打开主控面板
(sleep 2 && open "http://localhost:8000") &

# 启动同传服务
$PYTHON server.py
