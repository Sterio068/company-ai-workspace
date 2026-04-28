#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

EXCLUDES=(
  -g '!reports/**'
  -g '!.git/**'
  -g '!.claude/**'
  -g '!**/.claude/**'
  -g '!.venv*/**'
  -g '!**/.venv*/**'
  -g '!tmp/**'
  -g '!**/tmp/**'
  -g '!**/__pycache__/**'
  -g '!**/*.pyc'
  -g '!**/*.py[cod]'
  -g '!installer-run.command'
  -g '!**/installer-run.command'
  -g '!config-templates/.env'
  -g '!config-templates/.env.*'
  -g '!config-templates/data/**'
  -g '!config-templates/data-sandbox/**'
  -g '!config-templates/logs/**'
  -g '!config-templates/uploads/**'
  -g '!installer/dist/**'
  -g '!scripts/scan-white-label.sh'
  -g '!node_modules/**'
  -g '!frontend/launcher/node_modules/**'
  -g '!tests/e2e/node_modules/**'
)

echo "== White-label scan =="

if rg -uuu -n "承富|ChengFu|Chengfu|CHENGFU|chengfu" "${EXCLUDES[@]}" .; then
  echo "ERROR: old company branding remains in active source files." >&2
  exit 1
fi

OLD_NAME_MATCHES="$(find . \
  \( -path './reports' \
    -o -path './config-templates/logs' \
    -o -path './config-templates/uploads' \
    -o -path './config-templates/data' \
    -o -path './config-templates/data-sandbox' \
    -o -path './installer/dist' \
    -o -path './.git' \
    -o -path './.claude' \
    -o -path './.venv*' \
    -o -path './tmp' \
    -o -path '*/__pycache__' \
    -o -path './node_modules' \
    -o -path './frontend/launcher/node_modules' \
    -o -path './tests/e2e/node_modules' \
    -o -name '.env' \
    -o -name '.env.*' \
    -o -name 'installer-run.command' \) -prune -o \
  \( -name '*承富*' \
    -o -name '*ChengFu*' \
    -o -name '*Chengfu*' \
    -o -name '*CHENGFU*' \
    -o -name '*chengfu*' \) -print)"
if [[ -n "$OLD_NAME_MATCHES" ]]; then
  echo "$OLD_NAME_MATCHES"
  echo "ERROR: old company branding remains in active filenames." >&2
  exit 1
fi

if rg -uuu -n "examplepare|examplepile|examplebine|examplemonpath|examplemand|examplepletion|examplepute|examplepany|company-ai-ai|company_ai_ai" \
  "${EXCLUDES[@]}" .; then
  echo "ERROR: corrupted white-label replacement tokens remain." >&2
  exit 1
fi

echo "OK: active source files are white-labeled."
