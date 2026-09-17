#!/bin/zsh
set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/scripts/macos_app.py" stop
read -n 1 -s -r -p "按任意键关闭窗口。"
echo
