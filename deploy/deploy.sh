#!/usr/bin/env bash
#
# AiWork Backend 一键部署
#
# 用法 (在服务器上执行):
#   sudo bash deploy.sh
#
# 假设项目已 clone 到 /opt/aiwork-backend, .env 已配置好
# 会做的:
#   1. 装系统在依赖
#   2. 创建 deploy 用户 / 日志目录
#   3. 安装 systemd service (自启)
#   4. 装 nginx 配置
#   5. 启动并 enable

set -euo pipefail

KEY_="============= AiWork Backend deploy ============="
echo "$KEY_"
PROJECT_DIR=/opt/aiwork-backend
SERVICE_NAME=aiwork-backend
NGINX_CONF=/etc/nginx/conf.d/aiwork-backend.conf
LOG_DIR=/var/log/aiwork-backend

# 0. 须 root
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 请用 sudo/root 执行"
    exit 1
fi

# 1. 系统依赖
echo "[1/5] 装系统依赖..."
if command -v apt-get >/dev/null; then
    apt-get update -y
    apt-get install -y python3.11 python3.11-venv python3.11-dev nginx rsync
elif command -v yum >/dev/null; then
    yum install -y python3.11 python3.11-devel nginx rsync
fi

# 2. 创建 www-data 用户 / 日志目录
echo "[2/5] 准备用户与日志目录..."
id -u www-data >/dev/null 2>&1 || useradd --system --no-create-home --shell /usr/sbin/nologin www-data
mkdir -p "$LOG_DIR"
chown -R www-data:www-data "$LOG_DIR"

# 3. 移交项目所有权, 让 www-data 能读
chown -R www-data:www-data "$PROJECT_DIR"
chmod 640 "$PROJECT_DIR/.env"
chown www-data:www-data "$PROJECT_DIR/.env"

# 4. systemd service
echo "[3/5] 装 systemd service..."
cp "$PROJECT_DIR/deploy/aiwork-backend.service" /etc/systemd/system/$SERVICE_NAME.service
systemctl daemon-reload
systemctl enable --now $SERVICE_NAME
systemctl status $SERVICE_NAME --no-pager || true

# 5. nginx
echo "[4/5] 装 nginx 配置..."
cp "$PROJECT_DIR/deploy/aiwork-backend.nginx.conf" "$NGINX_CONF"
nginx -t
systemctl reload nginx

# 6. 验收
echo "[5/5] 部署完成, 验证..."
sleep 2
echo "--- 健康检查 (走 127.0.0.1) ---"
curl -sS http://127.0.0.1:8001/health || echo "[WARN] 服务还没好, 看 journalctl -u $SERVICE_NAME"

echo ""
echo "--- 公网访问 (要看你的防火墙放通 80) ---"
PUBLIC_IP=$(curl -sS https://api.ipify.org 2>/dev/null || echo "<your-public-ip>")
echo "    curl http://$PUBLIC_IP/health"

echo ""
echo "--- 常用命令 ---"
echo "  sudo systemctl status $SERVICE_NAME"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo "  sudo tail -f $LOG_DIR/err.log"
echo "  sudo nginx -t && sudo nginx -s reload"
echo ""
echo "$KEY_"
