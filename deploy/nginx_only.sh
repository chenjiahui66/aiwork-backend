#!/usr/bin/env bash
#
# 把 /api/ 反代追加到现有 aitools.conf 的 server 块里 (不破坏现有服务)
# 用法 (服务器上): sudo bash deploy/nginx_only.sh
#
# 实现:
#   1. 备份原文件
#   2. 用 grep -n '^}' 找 server 块的最后一行 (它必须是文件最后一个独立行的 })
#   3. 用 sed 在那一行之前插入 /api/ 反代 location 块
#   4. nginx -t 验证
#   5. 不 reload, 让你 review
#
# 不用 Python 解析嵌套 { } (之前那个有 bug, 害了用户一次, 绝不再用).

set -euo pipefail

PROJECT_DIR=/opt/aiwork-backend
AITOOLS_CONF=/etc/nginx/conf.d/aitools.conf
BACKUP_DIR=/etc/nginx/conf.d

if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 请用 sudo/root 执行"
    exit 1
fi

if [ ! -f "$AITOOLS_CONF" ]; then
    echo "[ERROR] 找不到 $AITOOLS_CONF, 你这台服务器可能不是标准的 conf.d 布局"
    echo "       请手动指定 NGINX_CONF 环境变量, 或先 cd 到项目根目录"
    exit 1
fi

# 0. 防重复
if grep -qF 'AiWork RAG Backend (auto-inserted' "$AITOOLS_CONF"; then
    echo "[跳过] aitools.conf 已经包含 AiWork RAG Backend location, 不重复插入"
    echo "       想强制重插, 先手动从 aitools.conf 删掉 # AiWork RAG Backend 那一段, 再跑本脚本"
    exit 0
fi

# 1. 备份
TS=$(date +%Y%m%d%H%M%S)
cp "$AITOOLS_CONF" "$BACKUP_DIR/aitools.conf.bak.$TS"
echo "[1/4] 备份完成: aitools.conf.bak.$TS"

# 2. 找 server 块的最后那个 } 行号
#    注意: nginx 配置通常缩进, 所以 } 前面可能有空格, 不能用 '^}'
LAST_LINE=$(grep -n '^\s*}' "$AITOOLS_CONF" | tail -n 1 | cut -d: -f1)
if [ -z "$LAST_LINE" ]; then
    echo "[ERROR] 找不到 server 块的闭合 }, 退出"
    echo "       可能文件结构非标准, 请手动检查 $AITOOLS_CONF"
    exit 1
fi
echo "[2/4] 找到最后一个 } 在第 $LAST_LINE 行"

# 3. 用 sed 在那一行之前插入 location 块
#    -i 是 in-place 编辑
#    ${LAST_LINE}i 是在 LAST_LINE 行之前插入
#    API_BLOCK 是要插入的内容 (here-doc, 双引号会展开变量, 但我们这里没有变量, 用 'EOF')
API_BLOCK=$(cat <<'BLOCK'
    # ===== AiWork RAG Backend (auto-inserted by deploy/nginx_only.sh) =====
    location /api/ {
        proxy_pass http://127.0.0.1:8001;

        # SSE 流式输出必须关闭缓冲, 否则 /api/chat 一个 token 都推不出来
        proxy_buffering off;
        proxy_cache off;

        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        gzip off;
    }

BLOCK
)

# sed 'Ni\' 在指定行 N 之前插入
# 用 awk 更稳: 直接在 N-1 行后输出 API_BLOCK + 原文件从 N 行开始
TMP=$(mktemp)
awk -v n="$LAST_LINE" -v block="$API_BLOCK" '
    NR == n { print block }
    { print }
' "$AITOOLS_CONF" > "$TMP"

# 校验行数变化 (多了一行 API_BLOCK 的内容, 大约 22 行)
NEW_LINES=$(wc -l < "$TMP")
OLD_LINES=$(wc -l < "$AITOOLS_CONF")
echo "[3/4] 行数变化 $OLD_LINES -> $NEW_LINES"

# 写回
mv "$TMP" "$AITOOLS_CONF"

# 4. nginx -t 验证
echo "[4/4] nginx -t 验证..."
if nginx -t; then
    echo "[OK] nginx 配置语法 OK"
else
    echo "[ERROR] nginx 配置有错, 准备回滚..."
    cp "$BACKUP_DIR/aitools.conf.bak.$TS" "$AITOOLS_CONF"
    echo "已回滚到 $BACKUP_DIR/aitools.conf.bak.$TS"
    exit 1
fi

# 5. 提示手动 reload
echo ""
echo "✅ nginx 配置已就位, 但不自动 reload"
echo ""
echo "👉  review 改动:"
echo "    diff $BACKUP_DIR/aitools.conf.bak.$TS $AITOOLS_CONF"
echo ""
echo "👉  reload:"
echo "    sudo nginx -s reload"
echo ""
echo "👉  验证:"
echo "    curl http://47.98.253.138/api/documents"
echo "    curl http://47.98.253.138/health"
echo ""
echo "回滚 (如果出问题):"
echo "    sudo cp $BACKUP_DIR/aitools.conf.bak.$TS $AITOOLS_CONF"
echo "    sudo nginx -s reload"