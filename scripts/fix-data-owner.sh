#!/usr/bin/env bash
# 修复 Li&Panel 数据目录属主：容器以 uid 10001 (appuser) 运行，
# Linux 部署时若 ./data 属主为 root，会报 "unable to open database file"。
# 用法：bash scripts/fix-data-owner.sh [数据目录，默认 ./data]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${1:-$ROOT/data}"

mkdir -p "$DATA_DIR"

if command -v docker >/dev/null 2>&1; then
  echo "==> 使用临时容器修正 ${DATA_DIR} 属主为 10001:10001"
  docker run --rm -v "${DATA_DIR}:/data" alpine chown -R 10001:10001 /data
else
  echo "==> 未找到 docker，尝试本机 chown（可能需要 sudo）"
  sudo chown -R 10001:10001 "$DATA_DIR"
fi

echo "PASS: ${DATA_DIR} 属主已修复，可重新执行 docker compose up -d"
