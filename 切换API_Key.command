#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -d ".venv" ]; then
    .venv/bin/python switch_key.py "$@"
else
    python3 switch_key.py "$@"
fi

echo ""
echo "----------------------------------------------------------"
read -p "按回车键退出窗口..."
