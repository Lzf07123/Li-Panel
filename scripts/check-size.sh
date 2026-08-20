#!/usr/bin/env bash
# V50 构建体积预算：dist/assets 总 JS/CSS 不超过 BUDGET（默认 2MB），记录基线。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUDGET="${SIZE_BUDGET:-2097152}"
TOTAL=0
for f in "$ROOT"/frontend/dist/assets/*.js "$ROOT"/frontend/dist/assets/*.css; do
  [ -f "$f" ] && TOTAL=$((TOTAL + $(wc -c < "$f")))
done
echo "assets 总大小: $TOTAL bytes (预算 $BUDGET)"
[ "$TOTAL" -le "$BUDGET" ] || { echo "FAIL: 超出体积预算"; exit 1; }
echo "PASS"
