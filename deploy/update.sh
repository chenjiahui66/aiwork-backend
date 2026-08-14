#!/usr/bin/env bash
#
# AiWork Backend 一键更新
# 用法 (服务器上): bash update.sh
#
# 思路: git pull → 重启 systemd service (uvicorn --reload 没用因为我们没用 --reload)

set -euo pipefail
PROJECT_DIR=/opt/aiwork-backend
SERVICE_NAME=aiwork-backend

cd "$PROJECT_DIR"

echo "[1/3] git pull..."
git pull --rebase --autostash

echo "[2/3] 装/更新依赖 (如有 requirements.txt 变化)..."
if [ -f requirements.txt ]; then
    .venv/bin/pip install -r requirements.txt
fi

echo "[3/3] 重启服务..."
sudo systemctl restart $SERVICE_NAME
sleep 2
sudo systemctl status $SERVICE_NAME --no-pager | head -n 5
echo ""
echo "--- 验证 ---"
curl -sS http://127.0.0.1:8001/health || echo "[WARN] 看 journalctl -u $SERVICE_NAME"
