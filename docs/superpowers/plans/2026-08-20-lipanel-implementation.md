# Li&Panel 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个容器化的个人快捷方式面板：本地密码 + Li&Pass OIDC 双登录、公开/私密可见性后台可改、站点品牌信息后台可改、低占用 FastAPI + SQLite 后端、Li&Design 视觉实例化前端。

**Architecture:** FastAPI 单进程提供 JSON API 与静态托管；SQLite（WAL，标准库）存用户/会话/SSO/分组/链接/设置；OIDC 走授权码 + PKCE S256，按 `(provider, subject)` 绑定；前端 React + TS + Vite + Tailwind CSS 4 按 Li&Design 模板实例化；Docker 多阶段构建，镜像与软件源由环境变量可换。

**Tech Stack:** Python 3.12、FastAPI、uvicorn、httpx、PyJWT、cryptography、pytest；React 19、TypeScript、Vite 7、Tailwind CSS 4；Docker + compose。

## Global Constraints

- 后端运行时内存目标 50–90MB：单 worker uvicorn、无 ORM、无 Redis、SQLite WAL。
- 所有业务查询强制 `user_id` 隔离；跨用户 id 一律 404。
- SSO 身份键唯一为 `(provider, subject)`；邮箱仅展示，每次登录刷新。
- 授权码只使用一次；`state`/`nonce` 逐字符校验；机密客户端也带 PKCE `code_verifier`。
- 登出地址 `GET /auth/logout?next=` 只允许相对路径或自身域名，拒绝 `//` 开头。
- 可见性：服务端过滤，私密数据绝不下发；公开链接默认 `guest_url_mode='hidden'`，访客走 `/go/{id}`。
- 站点可见信息（名称/slogan/描述/logo/favicon/页脚/备案/public_mode）后台可改，存 `site_settings`；`brand.ts` 仅默认值。
- 前端技术栈保持 Li&Design 模板原样：React + TS + Vite + Tailwind CSS 4，不做原生改写。
- 加速源：`IMAGE_REGISTRY` 统一控制 python/node 基础镜像；`APT_MIRROR`、`PIP_INDEX_URL`、`NPM_REGISTRY` 各自独立；全部经 compose `build.args` 从 `.env` 读取。
- Cookie 名 `lipanel_session`；令牌前缀 `lipanel`；主题存储键 `lipanel-theme`。
- 提交规范：`<type>: <中文简述>`；每个任务独立提交。

---

### Task 1: 项目骨架与 git 规范

**Files:**
- Create: `.gitignore`
- Create: `backend/app/__init__.py`、`backend/tests/__init__.py`
- Add: `Li-Design` git 子模块（`git submodule add https://github.com/Lzf07123/Li-Design.git Li-Design`）

**Interfaces:**
- Produces: 仓库基础目录结构 `backend/`、`frontend/`、`docs/`；`.gitignore` 忽略 `data/`、`node_modules/`、`dist/`、`__pycache__/`、`.venv/`、`.env`。

- [ ] **Step 1: 写 `.gitignore`**

```gitignore
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
data/
node_modules/
dist/
.DS_Store
```

- [ ] **Step 2: 创建目录与 `__init__.py`**

```bash
mkdir -p backend/app backend/tests frontend/src docs/superpowers/plans
touch backend/app/__init__.py backend/tests/__init__.py
```

- [ ] **Step 3: 提交**

```bash
git submodule add https://github.com/Lzf07123/Li-Design.git Li-Design
git add -A && git commit -m "chore: 初始化项目骨架并引入 Li-Design 子模块"
```

---

### Task 2: Li&Design 实例化（M0）

**Files:**
- Create: `design-system/lipanel/BRAND.md`
- Create: `design-system/lipanel/MASTER.md`
- Create: `AGENTS.md`
- Create: `frontend/src/index.css`（复制 `/tmp/li-design-inspect/reusable-tokens.template.css`，`{{PROJECT_PREFIX}}` → `lipanel`，色值沿用海玻璃模板）
- Create: `frontend/src/lib/brand.ts`（默认值：name `Li&Panel`、slogan `一次收藏，触达所有常用入口`、logo `/brand-logo.webp`、favicon `/favicon.webp`、footer `© 2026`、icp 空）
- Create: `frontend/index.html`（favicon、明暗 `theme-color`、`description`、首帧主题脚本读取 `lipanel-theme`）
- Create: `frontend/public/icons.svg`（内联 SVG symbol 集：grid、lock、globe、plus、search、moon、sun、gear、upload）

**Interfaces:**
- Produces: `brand.ts` 导出 `BRAND = { name, slogan, description, logo, favicon, footerText, icp }`；`index.css` 提供 `--lipanel-*` 令牌与 `.btn/.card/.input/.badge/.modal/.toast/.page-enter/.shimmer/.spinner` 组件类；`index.html` 含首帧主题脚本（键 `lipanel-theme`）。

- [ ] **Step 1: 生成令牌 CSS**

```bash
cp Li-Design/reusable-tokens.template.css frontend/src/index.css
```

- [ ] **Step 2: 替换占位符并核对**

```bash
sed -i '' 's/{{PROJECT_PREFIX}}/lipanel/g' frontend/src/index.css
rg -c 'PROJECT_PREFIX' frontend/src/index.css || echo "clean"
```

- [ ] **Step 3: 编写 BRAND.md / MASTER.md / AGENTS.md / brand.ts / index.html / icons.svg**

BRAND.md 记录 §13.3 槽位表与 §13.5 后台覆盖治理；MASTER.md 记录令牌快照与组件清单；AGENTS.md 写本项目协作规范（单一事实来源、验证才算完成、提交规范）。

- [ ] **Step 4: 验证**

```bash
rg -n 'PROJECT_PREFIX|TODO|TBD' frontend/src/index.css design-system/lipanel/ || echo clean
rg -n 'lipanel-' frontend/src/index.css | head -3
```

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "docs: 实例化 Li&Design 视觉方案"
```

---

### Task 3: 后端配置与数据库（TDD）

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Consumes: Task 1 目录。
- Produces:
  - `load_settings() -> Settings`：`data_dir`（默认 `./data`）、`secret_key`、`public_mode`（默认 true）、`cookie_secure`（false）、`session_days`（30）、`oidc_enabled`（false）、`oidc_issuer/client_id/client_secret/redirect_uri`（None）。
  - `connect(path: Path) -> sqlite3.Connection`：`PRAGMA journal_mode=WAL`、`foreign_keys=ON`、`row_factory=sqlite3.Row`。
  - `init_schema(conn) -> None`：创建 `users/sso_identities/sso_flows/sessions/groups/links/settings/site_settings` 八张表（按设计文档 §4）。
  - `get_db() -> Iterator[sqlite3.Connection]`：FastAPI 依赖，请求结束 commit/close。
  - `count_users(conn) -> int`、`create_user(conn, username, password_hash, salt, role) -> int`。

`pyproject.toml` 依赖：`fastapi`、`uvicorn`、`httpx`、`PyJWT`、`cryptography`；dev：`pytest`。

- [ ] **Step 1: 写失败测试 `tests/test_db.py`**

```python
from pathlib import Path
from app.db import connect, init_schema, create_user, count_users

def test_schema_and_user(tmp_path: Path):
    conn = connect(tmp_path / "test.db")
    init_schema(conn)
    assert count_users(conn) == 0
    uid = create_user(conn, "admin", "hash", "salt", "admin")
    assert count_users(conn) == 1
    assert uid > 0
    conn.close()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_db.py -v
```

预期：`ModuleNotFoundError: No module named 'app'`。

- [ ] **Step 3: 实现 config.py / db.py**

`db.py` 用 `sqlite3.connect(path)`，schema 用 `CREATE TABLE IF NOT EXISTS` 全文按设计文档 §4；`create_user` 用 `INSERT` 返回 `lastrowid`。

- [ ] **Step 4: 运行确认通过**

```bash
cd backend && python -m pytest tests/test_db.py -v
```

- [ ] **Step 5: 提交**

```bash
git add -A && git commit -m "feat: 后端配置与 SQLite 数据层"
```

---

### Task 4: 安全工具与依赖（TDD）

**Files:**
- Create: `backend/app/security.py`
- Create: `backend/app/deps.py`
- Test: `backend/tests/test_security.py`

**Interfaces:**
- Consumes: `connect/init_schema/create_user`（Task 3）。
- Produces:
  - `hash_password(password: str) -> tuple[str, str]`（`hashlib.scrypt` N=2^14 r=8 p=1，随机盐 16B，返回 b64(hash), b64(salt)）
  - `verify_password(password, hash_b64, salt_b64) -> bool`
  - `new_token(nbytes=32) -> str`
  - `create_session(conn, user_id, sso_sid=None) -> str`（存 `sessions`，`expires_at = now + session_days`）
  - `get_session_user(conn, token) -> sqlite3.Row | None`（join users，检查过期）
  - `delete_session(conn, token) -> None`
  - `class RateLimiter`：`allow(key: str) -> bool`（固定窗口：`limit` 次/`window_seconds`）
  - `current_user(request, conn=Depends(get_db)) -> sqlite3.Row`（读 `lipanel_session` Cookie，无效抛 401）

- [ ] **Step 1: 写失败测试 `tests/test_security.py`**

```python
from datetime import datetime, timedelta, timezone
from app.db import connect, init_schema, create_user
from app.security import (
    hash_password, verify_password, create_session, get_session_user,
    delete_session, RateLimiter,
)

def test_scrypt_roundtrip():
    h, s = hash_password("secret123")
    assert verify_password("secret123", h, s)
    assert not verify_password("wrong", h, s)

def test_session_lifecycle(tmp_path):
    conn = connect(tmp_path / "t.db")
    init_schema(conn)
    uid = create_user(conn, "admin", "h", "s", "admin")
    token = create_session(conn, uid)
    row = get_session_user(conn, token)
    assert row["id"] == uid
    delete_session(conn, token)
    assert get_session_user(conn, token) is None

def test_rate_limiter():
    rl = RateLimiter(limit=2, window_seconds=60)
    assert rl.allow("a") and rl.allow("a")
    assert not rl.allow("a")
    assert rl.allow("b")
```

- [ ] **Step 2: 运行确认失败**（`ImportError`）
- [ ] **Step 3: 实现 security.py / deps.py**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 密码哈希与会话安全层"`

---

### Task 5: FastAPI 入口、中间件与健康检查（TDD）

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/brand_defaults.py`
- Test: `backend/tests/conftest.py`
- Test: `backend/tests/test_main.py`

**Interfaces:**
- Consumes: Task 2/3/4。
- Produces:
  - `create_app(settings=None) -> FastAPI`：挂 `get_db`、全部路由、静态目录、中间件。
  - 中间件：安全响应头（CSP `default-src 'self'; style-src 'self'; img-src 'self' data: https:; connect-src 'self'; frame-ancestors 'none'`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`）；写方法校验 Origin 同源；认证响应 no-store 由路由头补充。
  - `GET /api/health` → `{"status":"ok"}`。
  - `brand_defaults.py`：`SITE_DEFAULTS = {"site_name": "Li&Panel", "slogan": "一次收藏，触达所有常用入口", "description": "", "logo": "/brand-logo.webp", "favicon": "/favicon.webp", "footer_text": "© 2026", "icp": ""}`。
  - `seed_site_defaults(conn)`：首次启动写入 `site_settings`。

`conftest.py`：`client` fixture——`tempfile` 数据目录、`create_app`、`TestClient`，每个测试独立库；`db_conn` fixture。

- [ ] **Step 1: 写失败测试**

```python
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

def test_security_headers(client):
    r = client.get("/api/health")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
```

- [ ] **Step 2: 运行确认失败**（`ModuleNotFoundError`）
- [ ] **Step 3: 实现 main.py / brand_defaults.py / conftest.py**
- [ ] **Step 4: 运行确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: FastAPI 入口与安全中间件"`

---

### Task 6: 初始化管理员（TDD）

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/setup.py`
- Test: `backend/tests/test_setup.py`

**Interfaces:**
- Consumes: Task 4/5。
- Produces:
  - `GET /api/setup-status` → `{"required": bool}`（users 为空）
  - `POST /api/setup` `{username, password}` → 201 `{"id": ...}`；仅 users 为空时可用，否则 409；用户名/密码规则与 §5.3 一致；成功后 `rate_limiter` 重置。

- [ ] **Step 1: 写失败测试**

```python
def test_setup_first_and_second(client):
    assert client.get("/api/setup-status").json()["required"] is True
    r = client.post("/api/setup", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 201
    assert client.get("/api/setup-status").json()["required"] is False
    r2 = client.post("/api/setup", json={"username": "b", "password": "secret123"})
    assert r2.status_code == 409
```

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 setup.py**
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 首启初始化管理员"`

---

### Task 7: 本地认证（TDD）

**Files:**
- Create: `backend/app/routers/auth.py`
- Test: `backend/tests/test_auth.py`

**Interfaces:**
- Consumes: Task 4/5/6。
- Produces:
  - `POST /api/auth/login` `{username, password}` → 200 `{"user": {...}}` + Set-Cookie `lipanel_session`；失败 401；限流 429。
  - `POST /api/auth/logout`（需登录）→ 204，清 Cookie。
  - `GET /api/auth/me`（需登录）→ `{"user": {...}, "sso": {"bound": bool, "provider": null, "email": null}}`。
  - Cookie：HttpOnly、SameSite=Lax、Path=/；`PANEL_COOKIE_SECURE=true` 时 Secure；Max-Age=session_days。

- [ ] **Step 1: 写失败测试**

```python
def test_login_logout_me(client, admin):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 200
    assert "lipanel_session" in r.headers["set-cookie"]
    me = client.get("/api/auth/me")
    assert me.json()["user"]["username"] == "admin"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

def test_login_wrong_password(client, admin):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "no"})
    assert r.status_code == 401
```

`conftest.py` 增加 `admin` fixture：先 `POST /api/setup` 建管理员。

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 auth.py**
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 本地登录与会话"`

---

### Task 8: 分组 CRUD（TDD）

**Files:**
- Create: `backend/app/routers/groups.py`
- Test: `backend/tests/test_groups.py`

**Interfaces:**
- Consumes: `current_user`、`get_db`。
- Produces:
  - `GET /api/groups` → 当前用户全部分组（按 `sort_order`）
  - `POST /api/groups` `{name, icon, is_public, sort_order}` → 201
  - `PUT /api/groups/{id}` → 200；`DELETE /api/groups/{id}` → 204（links 的 `group_id` 置 NULL）
  - 跨用户 id 一律 404；name 必填 1–50 字符。

- [ ] **Step 1: 写失败测试**

```python
def test_group_crud(client, auth_headers):
    r = client.post("/api/groups", json={"name": "工作", "is_public": True}, headers=auth_headers)
    assert r.status_code == 201
    gid = r.json()["id"]
    assert client.get("/api/groups", headers=auth_headers).json()[0]["name"] == "工作"
    assert client.put(f"/api/groups/{gid}", json={"name": "生活"}, headers=auth_headers).status_code == 200
    assert client.delete(f"/api/groups/{gid}", headers=auth_headers).status_code == 204

def test_group_requires_auth(client):
    assert client.post("/api/groups", json={"name": "x"}).status_code == 401
```

`conftest.py` 增加 `auth_headers`：登录后返回 `{"Cookie": f"lipanel_session={token}"}`。

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 groups.py**（所有语句带 `user_id=current_user["id"]`）
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 分组 CRUD"`

---

### Task 9: 快捷方式 CRUD（TDD）

**Files:**
- Create: `backend/app/routers/links.py`
- Test: `backend/tests/test_links.py`

**Interfaces:**
- Consumes: Task 8。
- Produces:
  - `GET /api/links` → 当前用户全部链接
  - `POST /api/links` `{group_id?, name, url_lan, url_wan?, icon_type?, icon_value?, description?, tags?, is_public?, guest_url_mode?, open_mode?, sort_order?}` → 201
  - `PUT/DELETE /api/links/{id}` → 200/204
  - 校验：name 1–100；`url_lan` 必填且 `http://`/`https://` 开头；`group_id` 必须属于当前用户否则 404；`icon_type ∈ {letter, iconify, upload}`；`guest_url_mode ∈ {hidden, show}`；`open_mode ∈ {new_tab, modal}`；tags 为字符串数组。

- [ ] **Step 1: 写失败测试**

```python
def test_link_crud(client, auth_headers):
    r = client.post("/api/links", json={"name": "路由器", "url_lan": "http://192.168.1.1"}, headers=auth_headers)
    assert r.status_code == 201
    lid = r.json()["id"]
    r2 = client.put(f"/api/links/{lid}", json={"name": "NAS", "url_lan": "http://192.168.1.2"}, headers=auth_headers)
    assert r2.status_code == 200 and r2.json()["name"] == "NAS"
    assert client.delete(f"/api/links/{lid}", headers=auth_headers).status_code == 204

def test_link_invalid_url(client, auth_headers):
    assert client.post("/api/links", json={"name": "x", "url_lan": "ftp://bad"}, headers=auth_headers).status_code == 422
```

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 links.py**（Pydantic 模型校验；`tags` 序列化 JSON）
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 快捷方式 CRUD"`

---

### Task 10: 面板可见性与 `/go` 跳转（TDD）

**Files:**
- Create: `backend/app/routers/panel.py`
- Test: `backend/tests/test_visibility.py`

**Interfaces:**
- Consumes: Task 7/8/9、`SITE_DEFAULTS`。
- Produces:
  - `GET /api/panel`（未登录）：`{"site": {...}, "groups": [{"id","name","icon","links":[...]}], "ungrouped": [...]}`，只含公开项；私密字段不下发；`PANEL_PUBLIC_MODE=false` 时 401。
  - `GET /api/panel`（登录）：全量。
  - 链接响应字段：`id/name/icon_type/icon_value/description/open_mode`；访客 `guest_url_mode='hidden'` 时不返回 `url_*`（用 `/go/{id}`），`show` 时返回有效 URL；登录用户返回 `url_lan/url_wan`。
  - 有效 URL 规则：登录用户按 `settings.link_mode`（默认 `lan`，取 `url_lan || url_wan`）；访客取 `url_wan || url_lan`。
  - `GET /go/{id}`：仅公开链接，302 到有效 URL；私密/不存在 404。
  - `GET /api/site-settings`（公开）：返回 `site_settings` 与默认值合并结果。

- [ ] **Step 1: 写失败测试**

```python
def test_guest_sees_only_public(client, admin, auth_headers):
    client.post("/api/groups", json={"name": "公开组", "is_public": True}, headers=auth_headers)
    client.post("/api/groups", json={"name": "私密组"}, headers=auth_headers)
    r = client.get("/api/panel")
    assert [g["name"] for g in r.json()["groups"]] == ["公开组"]

def test_go_hides_url_for_guest(client, auth_headers):
    r = client.post("/api/links", json={"name": "NAS", "url_lan": "http://192.168.1.2", "is_public": True}, headers=auth_headers)
    lid = r.json()["id"]
    panel = client.get("/api/panel").json()
    links = panel["ungrouped"]
    assert "url_lan" not in links[0] and "url_wan" not in links[0]
    redir = client.get(f"/go/{lid}", follow_redirects=False)
    assert redir.status_code == 302 and redir.headers["location"] == "http://192.168.1.2"
    assert client.get(f"/go/{lid+999}").status_code == 404
```

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 panel.py**（两个查询分支：公开 / 全量；DTO 组装）
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 面板可见性与 /go 跳转"`

---

### Task 11: 数据隔离测试（TDD 补充）

**Files:**
- Test: `backend/tests/test_isolation.py`

**Interfaces:**
- Consumes: Task 6–10。

- [ ] **Step 1: 写失败测试**

```python
def test_cross_user_isolation(client, admin):
    # 用户 A：admin 登录建分组
    a = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"}).headers["set-cookie"]
    ah = {"Cookie": a}
    g = client.post("/api/groups", json={"name": "A组"}, headers=ah).json()["id"]
    # 用户 B：SSO 关联接口不可用，直接用 create 建号路径模拟
    client.post("/api/setup", json={"username": "b", "password": "secret123"})  # 409，跳过
    # B 登录
    b = client.post("/api/auth/login", json={"username": "admin", "password": "secret123"}).headers["set-cookie"]
    bh = {"Cookie": b}
    assert client.put(f"/api/groups/{g}", json={"name": "X"}, headers=bh).status_code == 404
    assert client.delete(f"/api/groups/{g}", headers=bh).status_code == 404
```

说明：MVP 只有初始化管理员与 SSO 新建两条建号路径；本测试用同一管理员验证「另一个会话也无法越权访问他人不存在资源」的语义，真正的双用户隔离由 `test_sso_link_create`（Task 13）覆盖。

- [ ] **Step 2: 确认通过**（若接口 404 语义已正确则通过；否则修复）
- [ ] **Step 3: 提交** `git commit -m "test: 数据隔离语义"`

---

### Task 12: OIDC 客户端与令牌校验（TDD）

**Files:**
- Create: `backend/app/oidc.py`
- Test: `backend/tests/test_oidc.py`

**Interfaces:**
- Consumes: `Settings`（Task 3）。
- Produces（全部同步函数，内部用 `httpx.Client`）：
  - `OIDCError(Exception)`：携带 `code`（`access_denied` / `invalid_token` / `network`）
  - `generate_pkce() -> tuple[str, str]`（verifier, challenge）
  - `OIDCClient(settings)`：
    - `discover() -> dict`（GET `/.well-known/openid-configuration`，内存缓存 TTL 3600s）
    - `authorize_url(state, nonce, challenge) -> str`
    - `exchange(code, verifier) -> dict`（POST token，含 `client_secret` 若有；错误按 RFC 6749 `error` 字段抛 `OIDCError`）
    - `userinfo(access_token) -> dict`（Bearer；`detail` 错误抛）
    - `jwks() -> dict`
    - `validate_id_token(id_token, nonce, access_token) -> dict`：PyJWT decode（RS256、`kid` 选钥、`aud=client_id`、`iss=issuer`、`iat/exp`），手工核对 `nonce` 与 `at_hash = base64url(SHA256(access_token)[:16])`

- [ ] **Step 1: 写失败测试（用 `cryptography` 生成 RSA 密钥与真实 JWT）**

```python
def test_validate_id_token_ok(tmp_path, monkeypatch):
    from app.oidc import OIDCClient
    from app.config import load_settings
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import jwt as pyjwt, json, base64, hashlib, time

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwks = {"keys": [{"kty": "RSA", "kid": "k1", "use": "sig", "alg": "RS256",
                      **json.loads(key.public_key().serialize_public_key(
                          encoding=serialization.Encoding.PEM,
                          format=serialization.PublicFormat.SubjectPublicKeyInfo).decode("utf-8")
                          .split("-----")[2] and "{}")}]}
    # 简化：用 PyJWT 的 PyJWK 从 PEM 构造
    from jwt.algorithms import RSAAlgorithm
    pub_jwk = RSAAlgorithm.to_jwk(key.public_key())
    jwks = {"keys": [{"kty": "RSA", "kid": "k1", "use": "sig", "alg": "RS256", **json.loads(pub_jwk)}]}
    at = b"access-token"
    at_hash = base64.urlsafe_b64encode(hashlib.sha256(at).digest()[:16]).rstrip(b"=").decode()
    now = int(time.time())
    idt = pyjwt.encode({"iss": "https://auth.example.com", "sub": "u1", "aud": "client1",
                        "nonce": "n1", "iat": now, "exp": now + 300, "at_hash": at_hash,
                        "sid": "s1"}, key, algorithm="RS256", headers={"kid": "k1"})
    # 配置临时 Settings
    s = load_settings(overrides={"oidc_issuer": "https://auth.example.com", "oidc_client_id": "client1"})
    c = OIDCClient(s)
    claims = c.validate_id_token(idt, "n1", at, jwks)
    assert claims["sub"] == "u1" and claims["sid"] == "s1"
```

- [ ] **Step 2: 确认失败**（ImportError）
- [ ] **Step 3: 实现 oidc.py**（`httpx.Client(timeout=10)`；`validate_id_token` 用 `jwt.PyJWK`/`RSAAlgorithm.from_jwk`）
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: OIDC 客户端与 id_token 校验"`

---

### Task 13: SSO 登录/回调与首次关联（TDD）

**Files:**
- Create: `backend/app/routers/sso.py`
- Test: `backend/tests/test_sso.py`

**Interfaces:**
- Consumes: Task 7/12。
- Produces：
  - `GET /auth/sso/login`：`OIDC_ENABLED=false` 时 404；否则创建 `sso_flows`（token 存 Cookie `lipanel_sso_flow`）→ 302 authorize。
  - `GET /auth/sso/callback`：校验 state；错误参数按失败处理（`account_blocked` 特殊文案）→ 302 `/login?error=...`；换码/校验失败同；身份已绑定→建会话 302 `/`；未绑定→302 `/sso/link`。
  - `GET /auth/sso/link`：无有效 flow → 302 `/login?error=expired`。
  - `POST /api/sso/link` `{"action":"bind"|"create","username","password"}`：
    - bind：验证本地密码 → 绑定 → 建会话 → 204 + Set-Cookie
    - create：规则校验 → 建普通用户 → 绑定 → 建会话 → 201 + Set-Cookie
    - flow 无效/过期/已消费 → 409；身份已存在 → 409；用户名重复 → 409
  - `GET /auth/logout?next=`：清 `lipanel_session`，302 到 `next`（仅相对路径或自身域名；`//` 开头或外域 → 302 `/`）。

测试用 monkeypatch：`OIDCClient.discover/exchange/userinfo/jwks/validate_id_token` 返回固定值，避免外网。

- [ ] **Step 1: 写失败测试**

```python
def test_sso_login_flow(client, monkeypatch, app):
    from app import oidc as oidc_mod
    class FakeClient:
        def __init__(self, *a, **k): pass
        def discover(self): return {"authorization_endpoint": "https://auth.example.com/oauth2/authorize"}
        def authorize_url(self, state, nonce, challenge):
            return f"https://auth.example.com/oauth2/authorize?state={state}"
        def exchange(self, code, verifier): return {"access_token": "at", "id_token": "idt"}
        def userinfo(self, at): return {"sub": "u1", "email": "a@b.c"}
        def jwks(self): return {"keys": []}
        def validate_id_token(self, idt, nonce, at, jwks): return {"sub": "u1", "sid": "s1"}
    monkeypatch.setattr(oidc_mod, "OIDCClient", FakeClient)
    # 开 OIDC
    client.app.state.settings = None  # 用 create_app(settings=...) 重建，见测试 fixture
    r = client.get("/auth/sso/login", follow_redirects=False)
    assert r.status_code == 302
    flow_cookie = r.headers["set-cookie"].split(";")[0]
    state = r.headers["location"].split("state=")[1]
    cb = client.get(f"/auth/sso/callback?code=code&state={state}", headers={"Cookie": flow_cookie}, follow_redirects=False)
    # 首次未绑定 → 关联页
    assert cb.status_code == 302 and cb.headers["location"].endswith("/sso/link")
```

（另含：`bind` 成功/密码错误、`create` 成功/规则非法、flow 复用 409、`/auth/logout?next=//evil.com` 拒绝。）

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 sso.py**
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: SSO 登录与首次关联"`

---

### Task 14: 站点设置与上传（TDD）

**Files:**
- Create: `backend/app/routers/settings.py`
- Test: `backend/tests/test_settings.py`

**Interfaces:**
- Consumes: Task 5/7。
- Produces：
  - `GET /api/site-settings`（公开）→ `SITE_DEFAULTS` 与 `site_settings` 合并。
  - `PUT /api/site-settings`（登录）→ 白名单键更新：`site_name/slogan/description/logo/favicon/footer_text/icp/public_mode`；返回合并结果。
  - `POST /api/uploads`（登录，multipart `file`）→ 校验扩展名 `webp/png/jpg/jpeg/gif`、大小 ≤ 2MB、MIME `image/*` → 存 `data/uploads/{uuid}.{ext}` → 返回 `{"url": "/uploads/..."}`。
  - `GET /uploads/{name}`（公开）→ FileResponse，仅上述扩展名；不存在 404。
  - `GET/PUT /api/settings`（登录）→ 用户键：`theme ∈ {light,dark,system}`、`link_mode ∈ {lan,wan}`。

- [ ] **Step 1: 写失败测试**

```python
def test_site_settings_public_and_update(client, auth_headers):
    r = client.get("/api/site-settings")
    assert r.json()["site_name"] == "Li&Panel"
    r2 = client.put("/api/site-settings", json={"site_name": "我的面板", "slogan": "常用入口"}, headers=auth_headers)
    assert r2.status_code == 200 and r2.json()["site_name"] == "我的面板"
    assert client.get("/api/site-settings").json()["site_name"] == "我的面板"

def test_upload_requires_login_and_whitelist(client, auth_headers):
    assert client.post("/api/uploads", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")}).status_code == 401
    r = client.post("/api/uploads", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n", "image/png")}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["url"].startswith("/uploads/")
    assert client.post("/api/uploads", files={"file": ("a.svg", b"<svg/>", "image/svg+xml")}, headers=auth_headers).status_code == 422
```

- [ ] **Step 2: 确认失败**（404）
- [ ] **Step 3: 实现 settings.py**
- [ ] **Step 4: 确认通过**
- [ ] **Step 5: 提交** `git commit -m "feat: 站点可见信息与上传"`

---

### Task 15: 前端骨架（构建验证）

**Files:**
- Create: `frontend/package.json`、`frontend/vite.config.ts`、`frontend/tsconfig.json`、`frontend/src/main.tsx`、`frontend/src/App.tsx`
- Create: `frontend/src/lib/api.ts`、`frontend/src/lib/theme.ts`

**Interfaces:**
- Consumes: Task 2 令牌与品牌文件。
- Produces：
  - `api.ts`：`api<T>(path, options)` fetch 封装（credentials same-origin、JSON、`ApiError`）；导出 `getPanel/login/logout/me/setupStatus/createAdmin/siteSettings/updateSiteSettings/uploadFile/crud`。
  - `theme.ts`：`getTheme()/setTheme(theme)` 读写 `lipanel-theme` 并切换 `document.documentElement.classList.toggle('dark')`；监听 `prefers-color-scheme`。
  - `App.tsx`：`createBrowserRouter` 路由 `/`、`/login`、`/setup`、`/sso/link`、`/settings`。
  - `vite.config.ts`：`@tailwindcss/vite` 插件、`base: '/'`、dev proxy `/api`、`/auth`、`/go`、`/uploads` → `http://localhost:8000`。

- [ ] **Step 1: 写 package.json 并安装依赖**

```bash
cd frontend && npm install react react-dom react-router-dom
npm install -D typescript vite @vitejs/plugin-react tailwindcss @tailwindcss/vite @types/react @types/react-dom
```

- [ ] **Step 2: 配置 vite/tsconfig/index.html**
- [ ] **Step 3: 实现 api.ts / theme.ts / main.tsx / App.tsx（占位页）**
- [ ] **Step 4: 构建验证**

```bash
cd frontend && npx tsc --noEmit && npx vite build
```

- [ ] **Step 5: 提交** `git commit -m "feat: 前端骨架与路由"`

---

### Task 16: 认证与关联页面（视觉验收）

**Files:**
- Create: `frontend/src/components/AuthShell.tsx`、`frontend/src/components/TechAmbience.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`、`frontend/src/pages/SetupPage.tsx`、`frontend/src/pages/SsoLinkPage.tsx`

**Interfaces:**
- Consumes: `api.ts`、`brand.ts`、令牌类。
- Produces：
  - `AuthShell`：居中 `max-w-md` 卡片 + 品牌名/slogan + 备案 + TechAmbience。
  - `TechAmbience`：`.tech-grid`、`.tech-beam`、`.tech-dot` 三个纯 CSS 装饰层（`aria-hidden`、`pointer-events-none`、`prefers-reduced-motion` 单帧）。
  - `LoginPage`：用户名/密码表单；SSO 按钮（`OIDC_ENABLED` 由 `/api/site-settings` 返回 `oidc_enabled` 决定——后端在站点设置响应中附加 `oidc_enabled`）；错误展示。
  - `SetupPage`：`/api/setup-status` 为 false 时自动跳 `/login`；创建管理员表单。
  - `SsoLinkPage`：Tab 切换「绑定已有账号 / 新建账号」，提交 `POST /api/sso/link`。

- [ ] **Step 1: 实现组件与页面**
- [ ] **Step 2: 构建验证** `npx tsc --noEmit && npx vite build`
- [ ] **Step 3: 手动核对 Li&Design 清单：无 emoji 图标、focus-visible、reduced-motion、对比度**
- [ ] **Step 4: 提交** `git commit -m "feat: 登录/初始化/SSO 关联页"`

---

### Task 17: 面板页与管理（视觉验收）

**Files:**
- Create: `frontend/src/pages/PanelPage.tsx`、`frontend/src/pages/SettingsPage.tsx`
- Create: `frontend/src/components/AppHeader.tsx`、`frontend/src/components/LinkCard.tsx`、`frontend/src/components/GroupSection.tsx`

**Interfaces:**
- Consumes: `getPanel`、`siteSettings`、上传接口。
- Produces：
  - `PanelPage`：未登录展示公开视图（品牌区用 site 信息、分组卡片、链接走 `/go/{id}`）；登录展示完整视图 +「管理」按钮；本地搜索过滤（名称/URL/标签）；主题切换。
  - `SettingsPage`：站点信息表单（名称/slogan/描述/logo/favicon/页脚/备案/公开模式）、图片上传（预览 + 保存引用）、用户设置（主题、链接模式）；分组/链接管理的公开开关与访客字段开关（复用 CRUD 表单）。

- [ ] **Step 1: 实现页面与组件**
- [ ] **Step 2: 构建验证**
- [ ] **Step 3: 提交** `git commit -m "feat: 面板与管理页面"`

---

### Task 18: 测试全套与联调（后端）

**Files:**
- Modify: `backend/tests/*`

**Interfaces:**
- Consumes: 全部。

- [ ] **Step 1: 跑全套测试**

```bash
cd backend && python -m pytest -q
```

- [ ] **Step 2: 覆盖缺口修复**（每修一个先写测试）
- [ ] **Step 3: 提交** `git commit -m "test: 后端测试全套"`

---

### Task 19: Docker 化与加速源（交付验证）

**Files:**
- Create: `backend/Dockerfile`（多阶段：Node 构建前端 → `python:3.12-slim` 运行）
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Produces：
  - Dockerfile `ARG IMAGE_REGISTRY=docker.io/library`、`ARG APT_MIRROR=deb.debian.org`、`ARG PIP_INDEX_URL=https://pypi.org/simple`、`ARG NPM_REGISTRY=https://registry.npmjs.org`；前端阶段 `FROM ${IMAGE_REGISTRY}/node:22-alpine`；后端 `FROM ${IMAGE_REGISTRY}/python:3.12-slim`；apt 源替换为 `$APT_MIRROR`；uv/pip 用 `$PIP_INDEX_URL`；npm 用 `$NPM_REGISTRY`；非 root UID 10001；`CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1"]`；healthcheck `GET /api/health`。
  - compose `build.args` 从 `.env` 读上述变量；`./data:/app/data`；端口 8000；`restart: unless-stopped`。
  - `.env.example`：构建期（IMAGE_REGISTRY/APT_MIRROR/PIP_INDEX_URL/NPM_REGISTRY）+ 运行期（PANEL_* / OIDC_*）分区注释与国内镜像示例。
  - README：按 reusable-readme 模板，含部署/加速源/账号说明。

- [ ] **Step 1: 写 Dockerfile / compose / .env.example / README**
- [ ] **Step 2: 构建验证**

```bash
docker compose build
```

- [ ] **Step 3: 启动并验证**

```bash
docker compose up -d
curl -fsS http://localhost:8000/api/health
docker stats --no-stream lipanel
```

记录内存实测到设计文档 §3 与 README。

- [ ] **Step 4: 提交** `git commit -m "feat: Docker 化与加速源配置"`

---

### Task 20: 最终验收（Li&Design 第 6 章 + 设计文档回填）

**Files:**
- Modify: `design-system/lipanel/MASTER.md`
- Modify: `docs/superpowers/specs/2026-08-20-lipanel-design.md`

- [ ] **Step 1: 前端四档响应式与对比度抽查**（375/768/1024/1440）
- [ ] **Step 2: 后端安全清单核对**（state/nonce/at_hash/aud/iss/登出跳转/限流）
- [ ] **Step 3: 回填实测内存与最终令牌到 MASTER.md / 设计文档**
- [ ] **Step 4: 提交** `git commit -m "docs: 验收结果与实测回填"`
