#!/bin/bash
# ============================================================
# 承富 AI · Phase 1 Pilot 前交付包自檢
# ============================================================
# 用法:
#   ./scripts/pre-pilot-verify.sh
#
# 本腳本只驗證本地交付候選物一致性,不取代:
#   1. 乾淨 Mac/VM DMG 安裝驗收
#   2. LibreChat 原生 RAG/file_search 現場驗收
#   3. 4 人 Phase 1 pilot
#
# 安全原則:
#   - 不讀取、不列印、不保存任何密碼 / token / API key
#   - 只檢查敏感暫存檔是否存在
# ============================================================

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
REPORT_DIR="${ROOT_DIR}/reports/pre-pilot"
MANIFEST="${REPORT_DIR}/pre-pilot-readiness-${STAMP}.md"
DMG="${ROOT_DIR}/installer/dist/ChengFu-AI-Installer.dmg"
# 留空代表以最新 release manifest 追溯 DMG SHA。
# 不硬編當前 SHA:此腳本會被包進 DMG source snapshot,硬編會造成「改 SHA → DMG 又變」循環。
EXPECTED_DMG_SHA=""

PASS=0
FAIL=0
FAILED_STEPS=()
CURRENT_DMG_SHA=""

mkdir -p "$REPORT_DIR"

log() {
  echo "$@"
  echo "$@" >> "$MANIFEST"
}

run_check() {
  local name="$1"
  shift

  echo ""
  echo "═══ $name ═══"
  if "$@"; then
    echo "✅ $name"
    echo "- ✅ $name" >> "$MANIFEST"
    PASS=$((PASS + 1))
  else
    echo "❌ $name"
    echo "- ❌ $name" >> "$MANIFEST"
    FAILED_STEPS+=("$name")
    FAIL=$((FAIL + 1))
  fi
}

write_header() {
  cat > "$MANIFEST" <<EOF
# 承富 AI · Phase 1 Pilot 前交付包自檢 Manifest

時間:$(date '+%Y-%m-%d %H:%M:%S %Z')
Git HEAD:$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)
DMG:${DMG#$ROOT_DIR/}

## 自檢步驟
EOF
}

check_dmg_exists_and_sha() {
  [[ -f "$DMG" ]] || {
    echo "找不到 DMG:$DMG"
    return 1
  }

  CURRENT_DMG_SHA="$(shasum -a 256 "$DMG" | awk '{print $1}')"
  echo "DMG SHA-256:$CURRENT_DMG_SHA"

  if [[ -n "$EXPECTED_DMG_SHA" && "$CURRENT_DMG_SHA" == "$EXPECTED_DMG_SHA" ]]; then
    return 0
  fi

  local latest_manifest
  latest_manifest="$(ls -t "$ROOT_DIR"/reports/release/release-manifest-*.md 2>/dev/null | head -1 || true)"
  if [[ -n "$latest_manifest" ]] && grep -q "$CURRENT_DMG_SHA" "$latest_manifest"; then
    echo "DMG SHA 與固定值不同,但最新 release manifest 已記錄此 SHA。"
    return 0
  fi

  echo "DMG SHA 不符合固定交付候選值,最新 release manifest 也未記錄。"
  return 1
}

check_latest_release_manifest() {
  local latest_manifest
  latest_manifest="$(ls -t "$ROOT_DIR"/reports/release/release-manifest-*.md 2>/dev/null | head -1 || true)"

  [[ -n "$latest_manifest" ]] || {
    echo "找不到 reports/release/release-manifest-*.md"
    return 1
  }

  echo "Latest manifest:${latest_manifest#$ROOT_DIR/}"
  grep -q "結論:正式交付版驗收通過" "$latest_manifest" || {
    echo "release manifest 未包含正式交付版驗收通過結論"
    return 1
  }

  [[ -z "$CURRENT_DMG_SHA" ]] || grep -q "$CURRENT_DMG_SHA" "$latest_manifest" || {
    echo "release manifest 未記錄目前 DMG SHA"
    return 1
  }
}

check_final_delivery_audit() {
  local audit="$ROOT_DIR/reports/final-delivery-audit-2026-04-25.md"
  [[ -f "$audit" ]] || {
    echo "找不到 final delivery audit"
    return 1
  }

  grep -q "13 passed,0 failed" "$audit" || {
    echo "final delivery audit 未記錄 13 passed,0 failed"
    return 1
  }

  # 不要求 audit 寫死當前 SHA:
  # audit / this script 會被打進 DMG source snapshot,硬編當前 SHA 會造成
  # 「更新 SHA → DMG 內容改變 → SHA 又改」的自我引用循環。
  if [[ -n "$CURRENT_DMG_SHA" ]] && grep -q "$CURRENT_DMG_SHA" "$audit"; then
    return 0
  fi

  grep -Eq "release-manifest-\\*\\.md|最新.*release manifest|以最新.*DMG SHA" "$audit" || {
    echo "final delivery audit 未記錄 release manifest 追溯方式"
    return 1
  }

  echo "final delivery audit 以最新 release manifest 追溯 DMG SHA。"
}

check_required_docs() {
  local missing=0
  for path in \
    "$ROOT_DIR/docs/EXTERNAL-AUDIT-2026-04-25.md" \
    "$ROOT_DIR/docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md" \
    "$ROOT_DIR/docs/DAY0-DRY-RUN.md" \
    "$ROOT_DIR/docs/CHAMPION-WEEK1-LOG.md" \
    "$ROOT_DIR/docs/09-RAG-LAYERED-INDEX.md" \
    "$ROOT_DIR/reports/rag-verify/rag-verify-2026-04-28-100959.md"
  do
    if [[ ! -f "$path" ]]; then
      echo "缺文件:${path#$ROOT_DIR/}"
      missing=1
    fi
  done
  return "$missing"
}

check_gatekeeper_readme_in_dmg() {
  [[ -f "$DMG" ]] || return 1

  local mount_dir
  local result=0
  mount_dir="$(mktemp -d /tmp/chengfu-prepilot-dmg.XXXXXX)"

  if ! hdiutil attach -quiet -nobrowse -readonly -mountpoint "$mount_dir" "$DMG"; then
    rmdir "$mount_dir" >/dev/null 2>&1 || true
    echo "無法掛載 DMG"
    return 1
  fi

  if [[ ! -f "$mount_dir/讀我.txt" ]]; then
    echo "DMG 內缺 讀我.txt"
    result=1
  elif ! grep -Eq "右鍵|Control" "$mount_dir/讀我.txt"; then
    echo "讀我.txt 缺 Gatekeeper 右鍵/Control-click 說明"
    result=1
  fi

  hdiutil detach -quiet "$mount_dir" >/dev/null 2>&1 || true
  rmdir "$mount_dir" >/dev/null 2>&1 || true
  return "$result"
}

check_installer_api_key_links() {
  local missing=0
  local openai_url="https://platform.openai.com/api-keys"
  local anthropic_url="https://console.anthropic.com/settings/keys"
  local fal_url="https://fal.ai/dashboard/keys"

  for path in \
    "$ROOT_DIR/installer/ChengFu-AI-Installer.applescript" \
    "$ROOT_DIR/installer/install.sh" \
    "$ROOT_DIR/installer/build.sh" \
    "$ROOT_DIR/installer/README.md" \
    "$ROOT_DIR/scripts/setup-keychain.sh"
  do
    if [[ ! -f "$path" ]]; then
      echo "缺安裝檔:${path#$ROOT_DIR/}"
      missing=1
      continue
    fi
    for url in "$openai_url" "$anthropic_url" "$fal_url"; do
      if ! grep -q "$url" "$path"; then
        echo "${path#$ROOT_DIR/} 缺 API key 取得網址:$url"
        missing=1
      fi
    done
  done

  return "$missing"
}

check_sensitive_temp_files_absent() {
  local found=0
  for path in \
    "$ROOT_DIR/scripts/passwords.txt" \
    "$ROOT_DIR/config-templates/users.json"
  do
    if [[ -e "$path" ]]; then
      echo "敏感暫存檔不可存在:${path#$ROOT_DIR/}"
      found=1
    fi
  done
  return "$found"
}

check_test_artifacts_absent() {
  local found=0
  for path in \
    "$ROOT_DIR/test-results" \
    "$ROOT_DIR/tests/e2e/test-results" \
    "$ROOT_DIR/tests/e2e/playwright-report"
  do
    if [[ -d "$path" ]] && find "$path" -mindepth 1 -print -quit | grep -q .; then
      echo "測試暫存目錄仍有檔案:${path#$ROOT_DIR/}"
      found=1
    fi
  done
  return "$found"
}

check_diff_whitespace() {
  cd "$ROOT_DIR"
  git diff --check -- \
    AI-HANDOFF.md \
    docs/PHASE1-PILOT-VALIDATION-PACK-2026-04-25.md \
    reports/final-delivery-audit-2026-04-25.md \
    scripts/pre-pilot-verify.sh
}

write_footer() {
  {
    echo ""
    echo "## 結果"
    echo ""
    echo "- Passed:${PASS}"
    echo "- Failed:${FAIL}"
    if [[ -n "$CURRENT_DMG_SHA" ]]; then
      echo "- DMG SHA-256:${CURRENT_DMG_SHA}"
    fi
    echo "- Manifest:${MANIFEST#$ROOT_DIR/}"
    echo ""
    echo "## 仍需人工完成"
    echo ""
    echo "- 乾淨 Mac/VM DMG 安裝驗收"
    echo "- 乾淨機器上以去識別真實樣本複跑 LibreChat RAG/file_search 驗證"
    echo "- 老闆 + Champion + 2 PM 的 4 人 Phase 1 pilot"
    echo ""
    if [[ ${#FAILED_STEPS[@]} -gt 0 ]]; then
      echo "結論:不可進 Phase 1 pilot,請先修復失敗步驟。"
      echo ""
      echo "Failed Steps:${FAILED_STEPS[*]}"
    else
      echo "結論:本地交付包自檢通過,可安排乾淨 Mac/VM 與 Phase 1 現場驗收。"
    fi
  } >> "$MANIFEST"
}

write_header

run_check "DMG 存在且 SHA 可追溯" check_dmg_exists_and_sha
run_check "最新 release manifest 通過且記錄 SHA" check_latest_release_manifest
run_check "final delivery audit 記錄 release gate 與 manifest 追溯" check_final_delivery_audit
run_check "必要交付/驗收文件存在" check_required_docs
run_check "DMG 讀我含 Gatekeeper 右鍵開啟說明" check_gatekeeper_readme_in_dmg
run_check "安裝時 API Key 輸入畫面含取得網址" check_installer_api_key_links
run_check "敏感暫存檔不存在" check_sensitive_temp_files_absent
run_check "測試暫存 artifact 不存在" check_test_artifacts_absent
run_check "本次驗收包 diff 無 whitespace error" check_diff_whitespace

write_footer

echo ""
echo "Manifest:${MANIFEST}"
echo "Passed:${PASS}"
echo "Failed:${FAIL}"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
