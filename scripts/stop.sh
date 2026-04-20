#!/bin/bash
# ========================================
# 承富 AI 系統 · 停止腳本
# ========================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${PROJECT_DIR}/config-templates"

echo "停止 docker compose..."
docker compose down

echo "✅ 承富 AI 系統已停止"
echo ""
echo "注意:資料卷(對話、Agent、Mongo、Meili)保留於 ./data/,重啟時可恢復。"
echo "若要完全清除資料(⚠ 不可逆):"
echo "  cd config-templates && docker compose down -v && rm -rf data/"
