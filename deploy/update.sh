#!/usr/bin/env bash
#
# AiWork Backend 一键更新
# 用法 (服务器上): bash update.sh
#
# 思路: git pull → 重启 systemd service (uvicorn --reload 没用因为我们没用 --reload)
#
# 注意: git pull 不保留文件 owner, 所以 .env 权限必须重新 chown www-data,
#       否则 systemd service 起不来 (PermissionError).

set -euo pipefail
PROJECT_DIR=/opt/aiwork-backend
SERVICE_NAME=aiwork-backend
APP_USER=www-data

cd "$PROJECT_DIR"

echo "[1/4] git pull..."
git pull --rebase --autostash

echo "[2/4] 装/更新依赖 (如有 requirements.txt 变化)..."
if [ -f requirements.txt ]; then
    .venv/bin/pip install -r requirements.txt
fi

echo "[3/4] 修复文件 owner/权限 (git pull 不保留)..."
sudo chown -R "$APP_USER:$APP_USER" "$PROJECT_DIR"
[ -f "$PROJECT_DIR/.env" ] && sudo chmod 640 "$PROJECT_DIR/.env"
[ -d "$PROJECT_DIR/data" ] && sudo chown -R "$APP_USER:$APP_USER" "$PROJECT_DIR/data"
echo "    ✅ owner 修复完成"

echo "[4/4] 重启服务..."
sudo systemctl restart $SERVICE_NAME
sleep 3
sudo systemctl status $SERVICE_NAME --no-pager | head -n 8
echo ""
echo "--- 验证 ---"
curl -sS http://127.0.0.1:8001/health || echo "[WARN] 看 journalctl -u $SERVICE_NAME"