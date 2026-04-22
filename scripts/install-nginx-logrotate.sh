#!/bin/bash
# ============================================================
# [DEPRECATED] 承富 AI · nginx log rotation(host macOS)
# ============================================================
# R19 · 2026-04-23 已改走 docker logging driver(json-file max-size=20m)
# nginx access/error 改寫 stdout/stderr · docker 自動 rotate
# 本 script 保留給「若有 user 舊 mount /var/log/nginx/」時用 · 但新部署不需
#
# 原 R14#16 背景:
# nginx access/error log 寫在 docker volume ./logs/nginx/ · 沒 rotate 會 disk full
# macOS 用 newsyslog(不是 Linux 的 logrotate)
# 產出 /etc/newsyslog.d/chengfu-ai.conf · 每日 rotate · 保留 30 天
# 但:newsyslog rotate 後 nginx 仍寫舊 FD · 需 kill -USR1 才 reopen · 複雜
#
# 用法:
#   sudo ./scripts/install-nginx-logrotate.sh
#
# 驗證:
#   sudo newsyslog -nvv | grep chengfu
# ============================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${REPO_ROOT}/config-templates/logs/nginx"
NEWSYSLOG_CONF="/etc/newsyslog.d/chengfu-ai.conf"

if [[ "$EUID" -ne 0 ]]; then
    echo "❌ 需要 sudo(要寫 /etc/newsyslog.d/)"
    exit 1
fi

# newsyslog format:
# <filename>         <owner:group> <mode> <count> <size|KB> <when> <flags>
# -Z                 壓縮(gzip)
# 1024                 1MB 每 rotate(when)
# * = no size trigger
# @T00 = rotate at 00:00 daily
cat > "$NEWSYSLOG_CONF" << EOF
# 承富 AI · nginx access log · 每日 00:00 rotate · 保留 30 份 · gzip
$LOG_DIR/chengfu.access.log    $USER:staff   644  30    *    @T00  Z
$LOG_DIR/chengfu.error.log     $USER:staff   644  30    *    @T00  Z
EOF

echo "✅ 已寫 $NEWSYSLOG_CONF"
echo ""
echo "[驗證]:"
sudo newsyslog -nvv | grep -A2 chengfu || echo "  (尚未跑 · 00:00 自動 rotate)"
echo ""
echo "[手動測試(不等到午夜)]:"
echo "  sudo newsyslog -F -v"
