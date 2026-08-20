#!/usr/bin/env bash
# Li&Panel 端到端冒烟（V49）：干净数据目录 → 初始化 → 登录 → 建分组/链接 →
# 可见性 → 备份导出 → 备份导入 → 面板核对。全绿退出码 0。
set -euo pipefail

PORT="${SMOKE_PORT:-8011}"
BASE="http://127.0.0.1:${PORT}"
DATA_DIR="${SMOKE_DATA_DIR:-$(mktemp -d /tmp/lipanel-smoke.XXXXXX)}"
COOKIE_JAR="$(mktemp /tmp/lipanel-smoke-cookie.XXXXXX)"
BACKEND_PID=""
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -x "$ROOT/backend/.venv/bin/python" ]; then
  PY="${PYTHON:-$ROOT/backend/.venv/bin/python}"
else
  PY="${PYTHON:-python3}"
fi
JSON() { "$PY" -c 'import json,sys; d=json.load(sys.stdin); print(eval(sys.argv[1]))' "$1"; }

cleanup() {
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  rm -f "$COOKIE_JAR"
}
trap cleanup EXIT

echo "==> starting backend (${DATA_DIR}, port ${PORT})"
PANEL_DATA_DIR="$DATA_DIR" PANEL_PORT="$PORT" PANEL_SECRET_KEY="smoke-secret-0123456789abcdef" \
  "$PY" -m uvicorn --app-dir "$ROOT/backend" app.main:app --host 127.0.0.1 --port "$PORT" >/tmp/lipanel-smoke.log 2>&1 &
BACKEND_PID=$!

for _ in $(seq 1 30); do
  curl -fsS "$BASE/api/health" >/dev/null 2>&1 && break
  sleep 1
done
[ "$(curl -fsS "$BASE/api/health" | JSON "d['status']")" = "ok" ] || { echo "FAIL: 后端未就绪"; cat /tmp/lipanel-smoke.log; exit 1; }

echo "==> setup admin"
[ "$(curl -fsS -X POST "$BASE/api/setup" -H 'Content-Type: application/json' -d '{"username":"admin","password":"secret123"}' | JSON "d['id']")" -ge 1 ]

echo "==> login"
curl -fsS -c "$COOKIE_JAR" -X POST "$BASE/api/auth/login" \
  -H 'Content-Type: application/json' -d '{"username":"admin","password":"secret123"}' >/dev/null

echo "==> create group & link"
GID="$(curl -fsS -b "$COOKIE_JAR" -X POST "$BASE/api/groups" -H 'Content-Type: application/json' -d '{"name":"冒烟组","is_public":true}' | JSON "d['id']")"
LID="$(curl -fsS -b "$COOKIE_JAR" -X POST "$BASE/api/links" -H 'Content-Type: application/json' -d "{\"name\":\"冒烟链接\",\"url_lan\":\"http://127.0.0.1:${PORT}/api/health\",\"group_id\":$GID}" | JSON "d['id']")"

echo "==> visibility (public)"
curl -fsS -b "$COOKIE_JAR" -X PUT "$BASE/api/links/$LID" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"冒烟链接\",\"url_lan\":\"http://127.0.0.1:${PORT}/api/health\",\"group_id\":$GID,\"is_public\":true}" >/dev/null

echo "==> export backup"
curl -fsS -b "$COOKIE_JAR" "$BASE/api/backup" > /tmp/lipanel-smoke-backup.json
[ "$(JSON "len(d['links'])" < /tmp/lipanel-smoke-backup.json)" -ge 1 ]

echo "==> import backup (append)"
# 同名分组会合并复用（V19 设计），因此以「链接总数」断言追加成功
BEFORE="$(curl -fsS -b "$COOKIE_JAR" "$BASE/api/links" | JSON "len(d)")"
curl -fsS -b "$COOKIE_JAR" -X POST "$BASE/api/backup" \
  -H 'Content-Type: application/json' --data-binary @/tmp/lipanel-smoke-backup.json >/dev/null
AFTER="$(curl -fsS -b "$COOKIE_JAR" "$BASE/api/links" | JSON "len(d)")"
[ "$AFTER" -gt "$BEFORE" ] || { echo "FAIL: 导入未追加"; exit 1; }

echo "==> guest visibility (public only)"
GUEST_GROUPS="$(curl -fsS "$BASE/api/panel" | JSON "len(d['groups'])")"
[ "$GUEST_GROUPS" -ge 1 ]

echo "PASS: smoke ok (port ${PORT})"
rm -f /tmp/lipanel-smoke-backup.json
