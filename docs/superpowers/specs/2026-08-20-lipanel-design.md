# Li&Panel 设计文档

日期：2026-08-20

状态：待用户确认（确认后开始实现）

## 1. 目标

个人网页快捷方式面板（参考 Sun-Panel），核心诉求：

- 收集、分组、搜索网页快捷方式，支持图标与内/外网双地址
- 双登录方式：本地账号密码登录 + Li&Pass OIDC SSO 登录
- SSO 首次登录支持「绑定已有账号」或「新建账号」二选一
- 面板默认可被访客打开，但只展示公开内容；私密内容必须登录
- 低资源占用：单进程、SQLite、无外部数据库
- 容器化部署：多阶段构建，基础镜像与软件源通过环境变量可换加速源
- 视觉按个人方案 Li&Design 实例化，项目内生成自己的设计系统

## 2. 非目标（YAGNI）

- Docker 容器管理、系统监控、图库
- 多管理员 / 角色管理界面（MVP 只有初始化管理员；SSO 新建账号为普通用户，`role` 字段预留，暂不做管理界面）
- 开放注册接口（账号只能通过「初始化管理员」或「SSO 首次登录新建」产生）
- 前端技术栈改写：保持 Li&Design 模板默认的 React + TypeScript + Vite + Tailwind CSS 4
- 回程登出（Back-Channel Logout）与 RP 发起登出暂不做，首版用登出地址串跳满足 Li&Pass「登出通道至少二选一」

## 3. 技术栈

| 层 | 选择 | 理由 |
| --- | --- | --- |
| 语言/运行时 | Python 3.12 | 本机已有，FastAPI 生态成熟 |
| Web 框架 | FastAPI + uvicorn（单 worker） | 低占用，异步友好 |
| 数据库 | SQLite（标准库 `sqlite3`，WAL 模式） | 零外部服务，单文件 |
| ORM | 无（手写轻量数据访问层） | 减少依赖与内存 |
| 密码哈希 | `hashlib.scrypt`（标准库） | 免第三方加密库；N=2^14、r=8、p=1、随机盐 16B |
| 会话 | 随机不透明 token 存 `sessions` 表 + httpOnly Cookie | 可吊销，天然适配回程登出 |
| OIDC 客户端 | `httpx`（发现/换码/userinfo/JWKS）+ `PyJWT` + `cryptography` | 满足 RS256 验签 |
| 前端 | React + TypeScript + Vite + Tailwind CSS 4（按 Li&Design 模板原样） | 与模板/Li&Pass 一致，不做改写 |
| 测试 | pytest + fastapi TestClient | 认证与可见性是核心，必须有测试 |
| 部署 | Docker 多阶段构建 + compose，数据卷挂载，加速源环境变量 | 一键部署，实测内存约 46MiB（2026-08-20） |

## 4. 数据模型

```sql
users           (id INTEGER PK, username TEXT UNIQUE COLLATE NOCASE,
                 password_hash, salt, role DEFAULT 'user', created_at)

sso_identities  (id INTEGER PK, user_id REFERENCES users,
                 provider TEXT,            -- 'lipass'
                 subject TEXT,             -- Li&Pass sub（UUID，终身不变）
                 email TEXT, nickname TEXT, avatar TEXT,  -- 仅展示，每次登录刷新
                 created_at, last_login_at,
                 UNIQUE(provider, subject))

sso_flows       (id INTEGER PK, token TEXT UNIQUE,  -- 一次性关联流程凭证
                 state TEXT, nonce TEXT, code_verifier TEXT,
                 redirect_after TEXT, expires_at, consumed INTEGER DEFAULT 0,
                 created_at)

sessions        (id INTEGER PK, token TEXT UNIQUE, user_id,
                 sso_sid TEXT NULL,        -- 门户会话 id，供回程登出定位
                 expires_at, created_at, last_used_at)

groups          (id INTEGER PK, user_id, name, icon,
                 is_public INTEGER DEFAULT 0, sort_order, created_at)

links           (id INTEGER PK, user_id, group_id INTEGER NULL,
                 name, url_lan, url_wan,
                 icon_type TEXT DEFAULT 'letter',  -- letter / iconify / upload
                 icon_value TEXT,
                 description TEXT, tags TEXT,      -- tags 为 JSON 数组文本
                 is_public INTEGER DEFAULT 0, sort_order,
                 guest_url_mode TEXT DEFAULT 'hidden',  -- hidden / show
                 open_mode TEXT DEFAULT 'new_tab', -- new_tab / modal
                 created_at)

settings        (user_id, key, value, UNIQUE(user_id, key))

site_settings   (key TEXT PK, value TEXT, updated_at)
                -- 全局可见信息：site_name / slogan / description /
                -- logo / favicon / footer_text / icp / public_mode
```

硬性约束：

- 所有业务查询强制带 `user_id`，用户间数据严格隔离
- SSO 身份键一律 `(provider, subject)`，绝不使用邮箱作为主键（Li&Pass 邮箱可变）
- 删除分组时**不级联删除链接**：`links.group_id` 置 NULL，链接保留为「未分组」
- 私密默认：新增分组/链接 `is_public=0`

## 5. 认证与会话

### 5.1 本地登录

- `POST /api/auth/login`：scrypt 校验 → 建会话 → 下发 Cookie `lipanel_session`
- Cookie 属性：HttpOnly、SameSite=Lax；HTTPS 部署时经 `PANEL_COOKIE_SECURE=true` 加 Secure
- 会话有效期默认 30 天（`PANEL_SESSION_DAYS`），到期强制重新登录
- `POST /api/auth/logout`：删除当前会话
- `GET /api/auth/me`：返回当前用户与 SSO 绑定状态
- 登录接口限流：10 次/分钟/IP

### 5.2 SSO 登录（Li&Pass，授权码 + PKCE S256）

前置：`OIDC_ENABLED=true` 时登录页出现「Li&Pass SSO 登录」按钮。

`GET /auth/sso/login`：

1. 从 `/.well-known/openid-configuration` 读取端点（缓存 TTL 1 小时，不手写拼接）
2. 生成 `code_verifier` / `code_challenge`（S256）、`state`、`nonce`
3. 写入 `sso_flows`（token、10 分钟过期、一次性），Cookie `lipanel_sso_flow` 指向该流程
4. 302 到 authorize，scope 为 `openid profile email`

`GET /auth/sso/callback`：

1. 校验 `state` 与 `sso_flows` 一致；`error=access_denied`（含 `error_description=account_blocked`）一律按失败处理，302 回登录页并展示原因
2. `code + code_verifier`（机密客户端另加 `client_secret`）换令牌；授权码仅一次使用
3. 校验 id_token：JWKS 按 `kid` 选钥、RS256、`iss` 等于 issuer、`aud` 等于 client_id、`nonce` 一致、`iat/exp` 有效、`at_hash` 等于 `base64url(SHA256(access_token)[:16])`
4. 用 access_token 调 userinfo 取 `sub`（access_token 的 aud 是 userinfo 端点，不按 client_id 校验）
5. 查 `sso_identities(provider='lipass', subject=sub)`：
   - 命中 → 刷新 email/nickname/avatar → 建本地会话（记录 `sso_sid`）→ 302 到 `/`
   - 未命中 → 302 到 `/sso/link`（携带流程 Cookie），进入关联流程

### 5.3 首次 SSO 关联（绑定已有账号 / 新建账号）

`GET /auth/sso/link`：展示关联页（AuthShell），要求存在未过期、未消费的 `sso_flows`。

`POST /api/sso/link`（无需登录，但必须有有效流程）：

| 动作 | 入参 | 行为 |
| --- | --- | --- |
| `bind` | 用户名 + 本地密码 | 校验本地账号密码 → 绑定 `sso_identities` → 登录 |
| `create` | 用户名 + 密码 | 校验规则 → 新建普通用户 → 绑定 `sso_identities` → 登录 |

安全要求：

- 绑定已有账号必须验证本地密码，防止他人用 SSO 身份占号
- 流程一次性：成功后 `sso_flows.consumed=1`，重复使用返回 409
- 身份已存在返回 409；用户名重复返回 409
- 用户名规则：3–32 位字母/数字/`_`/`-`；密码至少 8 位
- 除初始化管理员外，**这是唯一的新建账号路径**，无公开注册接口

### 5.4 解绑 / 换绑（P1）

个人设置页显示 SSO 绑定状态；`DELETE /api/sso/identity` 解绑（需本地密码确认），解绑不删除本地账号；换绑 = 解绑后重新走 5.3。

### 5.5 登出

- 本地登出 `POST /api/auth/logout`：只清本站会话，不动门户会话
- 登出地址（`logout_uri`）`GET /auth/logout?next=...`：清 Cookie 后 302 到 `next`，只允许相对路径或自身域名，拒绝 `//` 开头的外部跳转
- RP 发起登出（`end-session`）：P1，需在门户登记登出回跳白名单
- 回程登出：P2（需公网 HTTPS），届时按 `logout_token` 校验并按 `(sub, sid)` 下线

## 6. 可见性与权限

- `groups.is_public`、`links.is_public` 默认 0（私密）
- 未登录 `GET /api/panel`：只返回「分组公开 且 链接公开」的内容；未分组的公开链接归入「未分组」区；服务端过滤，私密字段绝不下发
- 登录后 `GET /api/panel`：返回全部
- `PANEL_PUBLIC_MODE=false` 时关闭访客视图：未登录访问面板接口返回 401，前端跳登录页
- 所有写接口要求登录，且只能操作本人数据（跨用户 id 一律 404）
- **可见信息后台可改（管理界面核心能力）**：
  - 登录后的管理视图为每个分组/链接提供「公开/私密」开关，随时切换，修改立即生效于访客视图，无需重启
  - 每个公开链接可独立设置访客看到的字段：默认隐藏原始 URL，访客点击走 `GET /go/{id}` 服务端跳转（不暴露内网地址）；后台可改为「直接显示 URL」
  - 访客视图总开关（`PANEL_PUBLIC_MODE`）除环境变量外，也可在后台设置页切换（环境变量为初始值，运行时以设置页为准）
  - **站点品牌与可见信息后台可改**：站点名称、slogan、描述、Logo、favicon、页脚文案、备案号全部可在后台设置页编辑并即时生效；Logo/favicon 通过上传接口替换（登录后上传，存 `data/uploads/`，访客可公开访问图片本身）
  - `brand.ts` 仅作为设计默认值与回退值，运行时以 `site_settings` 覆盖为准（覆盖规则见 §13.5）

## 7. API 一览

### 公开

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/health` | 健康检查（容器 healthcheck 用） |
| `GET /api/panel` | 访客公开视图 |
| `GET /go/{id}` | 公开链接服务端跳转（隐藏原始地址；仅公开链接可用，私密/不存在返回 404） |
| `GET /uploads/{path}` | 上传的 Logo/favicon 等公开静态资源（仅图片类） |
| `GET /setup`、`POST /api/setup` | 首启初始化管理员；仅 `users` 为空时可用 |
| `GET /auth/sso/login` | 发起 SSO 授权 |
| `GET /auth/sso/callback` | 授权回调（门户白名单登记此地址） |
| `GET /auth/sso/link`、`POST /api/sso/link` | 首次 SSO 关联页与提交 |
| `GET /auth/logout?next=` | 登出地址（串跳清会话） |

### 需登录

| 方法与路径 | 说明 |
| --- | --- |
| `POST /api/auth/login`、`POST /api/auth/logout`、`GET /api/auth/me` | 本地认证 |
| `GET /api/panel` | 完整视图 |
| `GET/POST /api/groups`、`PUT/DELETE /api/groups/{id}` | 分组 CRUD |
| `GET/POST /api/links`、`PUT/DELETE /api/links/{id}` | 快捷方式 CRUD |
| `GET/PUT /api/settings` | 个人设置（主题等）；后台可改 `public_mode`、默认可见性 |
| `GET/PUT /api/site-settings` | 站点可见信息：名称/slogan/描述/logo/favicon/页脚/备案 |
| `POST /api/uploads` | 上传 Logo/favicon（仅登录；白名单图片类型与大小限制） |

### P1

| 方法与路径 | 说明 |
| --- | --- |
| `GET /api/sso/status`、`DELETE /api/sso/identity` | SSO 绑定状态与解绑 |
| `GET/POST /api/backup` | JSON 导出/导入 |

错误约定：统一 JSON `{"error": "..."}`；401 未登录、403 无权限、404 用户域内不存在、409 冲突、422 校验失败、429 限流。

### 7.1 页面映射

| 页面 | 路由 | 外壳 | 说明 |
| --- | --- | --- | --- |
| 初始化 | `/setup` | AuthShell | 首启创建管理员 |
| 登录 | `/login` | AuthShell | 密码登录 + SSO 按钮（OIDC 开启时） |
| 关联 | `/sso/link` | AuthShell | 绑定已有账号 / 新建账号 |
| 面板 | `/` | AppHeader + 内容区 | 未登录=公开视图；登录=完整视图 |
| 设置 | `/settings` | AppHeader | 站点信息（名称/slogan/描述/logo/favicon/页脚/备案）、公开模式、默认可见性、个人主题 |

## 8. 配置（环境变量）

### 8.0 运行期

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `PANEL_DATA_DIR` | `./data` | SQLite 与上传文件目录 |
| `PANEL_SECRET_KEY` | 必填 | 流程凭证与安全相关派生 |
| `PANEL_PUBLIC_MODE` | `true` | 是否允许访客公开视图（初始值；后台设置页可改，运行时以后台为准） |
| `PANEL_COOKIE_SECURE` | `false` | HTTPS 部署时设 `true` |
| `PANEL_SESSION_DAYS` | `30` | 会话有效期 |
| `OIDC_ENABLED` | `false` | 开启后登录页显示 SSO 按钮 |
| `OIDC_ISSUER` | — | Li&Pass issuer |
| `OIDC_CLIENT_ID` | — | 门户注册的客户端 ID |
| `OIDC_CLIENT_SECRET` | — | 机密客户端时填写 |
| `OIDC_REDIRECT_URI` | — | 必须与门户白名单逐字符一致 |

### 8.1 构建期加速源（Dockerfile / compose 可替换）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `IMAGE_REGISTRY` | `docker.io/library` | 两个基础镜像共用同一个加速前缀；如 `docker.m.daocloud.io/library`、`mirror.ccs.tencentyun.com/library`；compose 据此拼出完整镜像名 |
| `APT_MIRROR` | `deb.debian.org` | apt 源主机名（如 `mirrors.aliyun.com`、`mirrors.tuna.tsinghua.edu.cn`、`mirrors.ustc.edu.cn`） |
| `PIP_INDEX_URL` | `https://pypi.org/simple` | pip/uv 包索引（uv 同时读 `UV_INDEX_URL`） |
| `NPM_REGISTRY` | `https://registry.npmjs.org` | npm 源（如 `https://registry.npmmirror.com`） |

加速源属构建期参数：Dockerfile `ARG`/`ENV` + compose `build.args` 注入；运行期配置（`PANEL_*`、`OIDC_*`）走运行时环境变量。两者在 `.env.example` 中分区注释，互不混淆。

## 9. 安全设计

- Cookie：HttpOnly + SameSite=Lax（+ Secure 可选），会话过期兜底
- CSRF：SameSite=Lax + 所有写接口校验 Origin 同源；MVP 不引入额外 CSRF token
- 限流：登录、SSO 回调、初始化接口 10 次/分钟/IP（内存滑动窗口）
- 密码：scrypt（N=2^14、r=8、p=1、随机盐 16B）；用户名/密码规则见 5.3
- 响应头：CSP `default-src 'self'; style-src 'self'; img-src 'self' data: https:; connect-src 'self'; frame-src 'self' https: http:; frame-ancestors 'none'`；`X-Content-Type-Options: nosniff`；`Referrer-Policy: no-referrer`；认证响应 `Cache-Control: no-store`（`frame-src` 于 V07 内置窗口打开方式时加入，仅允许 https/http 站点被内嵌，本站仍禁止被他人 iframe）
- OIDC 对齐 Li&Pass 验收清单：
  - `state` / `nonce` 逐字符校验
  - `error=access_denied`（含 `account_blocked`）按失败处理
  - 机密客户端同样携带 PKCE `code_verifier`
  - id_token 完整校验：`kid` 选钥 / RS256 / `iss` / `aud` / `nonce` / `iat` / `exp` / `at_hash`
  - access_token 仅用于 userinfo，aud 不按 client_id 校验
  - 授权码一次性使用
  - 登出地址仅跳相对路径/自身域名，拒绝 `//`
  - 流程凭证 10 分钟过期、一次性

## 10. 测试计划

- 本地认证：登录成功/密码错误/限流/登出/me；Cookie 属性
- 初始化：首启成功、`users` 非空后拒绝
- SSO：完整成功路径；`state` 不符、`nonce` 不符、id_token 验签失败/`aud` 错/`iss` 错/`at_hash` 错、换码失败、userinfo 失败、`account_blocked`、流程过期、流程重复使用
- 关联：`bind` 成功、密码错误拒绝、`create` 成功、用户名重复/规则非法、身份已存在 409
- 可见性：访客只拿到公开分组/链接；私密字段绝不下发；未分组公开链接可见；`PANEL_PUBLIC_MODE=false` 后访客不可见
- 后台可见性管理：切换公开/私密后访客视图立即变化；`/go/{id}` 对公开链接跳转、对私密/不存在返回 404；`guest_url_mode` 隐藏/显示切换生效
- 站点可见信息：未登录可读默认值；登录后 `GET/PUT /api/site-settings` 可改并即时反映到访客视图；上传接口需登录、白名单类型、大小限制、不可上传脚本/HTML
- 品牌覆盖：`site_settings` 非空时覆盖 `brand.ts` 默认值；清空后回退默认
- 数据隔离：用户 B 读写用户 A 的分组/链接一律 404
- 分组/链接 CRUD：校验、排序、删除分组后链接保留为未分组
- 设置：按用户隔离
- 前端：`tsc` 类型检查 + `vite build` 通过；Li&Design 第 6 章清单核对

## 11. 部署

- Dockerfile 多阶段：前端阶段（Node + Vite 产物）→ 后端阶段（`python:3.12-slim`，uv 安装依赖，非 root UID 10001，uvicorn 单 worker）
- 加速源：`IMAGE_REGISTRY`（两基础镜像共用）、`APT_MIRROR`、`PIP_INDEX_URL`、`NPM_REGISTRY` 全部可替换
- `compose.yaml`：`./data:/app/data`，端口默认 8000（`PANEL_PORT` 可调，容器内与宿主机同一数值），`restart: unless-stopped`，healthcheck `GET /api/health`
- `.env.example`：集中列出全部构建期与运行期变量及国内加速源示例
- README 按 Li&Design 的 `reusable-readme.template.md` 生成，不留空占位符
- 生产建议前置 Caddy/nginx 反代启用 HTTPS，并设 `PANEL_COOKIE_SECURE=true`

## 12. 本次构建范围

M0（Li&Design 实例化）：

1. `design-system/lipanel/BRAND.md`（22 项槽位）与 `MASTER.md`
2. `frontend/src/index.css`（令牌，前缀 `lipanel`）、`frontend/src/lib/brand.ts`、`frontend/index.html` 品牌位
3. `frontend/public/` 品牌资产（Logo 素材待用户提供，先文字徽标占位）
4. 项目根 `AGENTS.md`

M1（后端骨架）：

5. FastAPI + SQLite 数据层 + 初始化管理员
6. 本地登录/登出/会话 + 限流 + 安全响应头
7. 分组与快捷方式 CRUD + 公开/私密可见性 + 后台可见性管理（公开开关、访客字段、`/go` 跳转）
8. 站点可见信息管理（名称/slogan/描述/logo/favicon/页脚/备案、上传接口、公开模式与默认可见性设置）

M2（SSO）：

9. Li&Pass PKCE 授权码流程 + id_token 完整校验
10. 首次关联：绑定已有账号 / 新建账号
11. 登出地址（logout_uri）

M3（交付）：

12. pytest 测试全套
13. Dockerfile + compose.yaml + `.env.example` + README
14. 容器内存实测（`docker stats`）回填本文档（实测 45.78MiB / 0.19% CPU，已完成）

P1 后续：解绑/换绑、RP 发起登出、回程登出、图标库/上传、内/外网切换、搜索增强、备份导入导出。

## 13. 视觉设计：Li&Design 实例化

视觉方案来源为个人模板仓库 `Lzf07123/Li-Design`（V1.2）。按模板使用边界，首次设计时在本项目内生成自己的设计方案，模板仓库不作为运行时依赖。

### 13.1 必交产出

| 产出物 | 位置 | 说明 |
| --- | --- | --- |
| 项目品牌方案 | `design-system/lipanel/BRAND.md` | 品牌内核 + 22 项槽位（含决策理由） |
| 实现速览 | `design-system/lipanel/MASTER.md` | 令牌、组件、页面模式落地快照 |
| 令牌落地 | `frontend/src/index.css` | 复制模板令牌，前缀 `lipanel`，填色值 |
| 品牌单点 | `frontend/src/lib/brand.ts` | 名称 / slogan / Logo / 备案的**设计默认值**出处（运行时后台覆盖见 §13.5） |
| 浏览器品牌位 | `frontend/index.html` | favicon、明暗 `theme-color`、`description`、首帧主题脚本 |
| 品牌资产 | `frontend/public/` | `brand-logo.webp`、`favicon.webp`、`icons.svg` |
| 项目协作手册 | `AGENTS.md`（项目根） | 参照模板 AGENTS.md 写本项目协作规范 |

### 13.2 技术栈（按模板原样，不做改写）

- React + TypeScript + Vite + Tailwind CSS 4；令牌落地 `frontend/src/index.css`（`@theme` + `:root`/`.dark` 明暗两套）；品牌单点保留 `brand.ts`
- 组件按模板第 5 章移植：`.btn/.card/.input/.badge/.modal/.toast` 等，只移植本项目需要的组件；gsap 依赖组件（PillTabs/MagicBento）确认体积与 CSP 后再引入
- 动效铁律：只动 `transform/opacity/background-position`，每个 `animation` 有对应 `@keyframes`，尊重 `prefers-reduced-motion`
- 生产 CSP `style-src 'self'`（Tailwind 构建产物），构建链只在开发/发布期，容器运行内存保持低占用

### 13.3 槽位草案（待用户确认）

| # | 槽位 | 草案 |
| --- | --- | --- |
| 1 | 项目显示名 | `Li&Panel` |
| 2 | 技术标识 | `lipanel`（Cookie/目录/卷名统一） |
| 3 | 一句话定位 | 一次收藏，触达所有常用入口 |
| 4 | 品牌承诺 | 常用入口，一次打开；私密内容，只属于你 |
| 5 | 人格比喻 | 安静的私人领航员 |
| 6 | 符号隐喻 | 直线=收藏路径、Z 形=面板入口、方块=快捷方式卡片、锁钥=私密内容、光斑=访问会话 |
| 7–12 | 主色/中性色/语义色/焦点环 | 沿用 Li& 家族海玻璃全淡色系（浅 `#25786D` / 深 `#7FD4C6` 等） |
| 13–14 | 字体 | Inter → 系统栈 → PingFang SC；不加载远程字体 |
| 15 | Logo/favicon | 待用户提供或授权生成；先用文字徽标占位 |
| 16 | 令牌前缀 | `lipanel` |
| 17 | 主题存储键 | `lipanel-theme` |
| 18 | slogan/备案 | slogan 定稿后写入 `brand.ts`；备案上线前留空 |
| 19 | 氛围浓度 | 认证页 10+光效默认；面板视图 10（soft）；后台 4×0.5 |
| 20 | 浏览器品牌位 | 按模板 §4.1 配置 |
| 21 | 强调色板 | 沿用模板六色板（ice/aqua/lilac/sage/mint/sand），稳定哈希分配瓦片色 |
| 22 | 按钮与光效 | 半透明单色按钮 + 细描边；光效「可见但克制」 |

### 13.4 验收对齐

实现完成后按模板第 6 章 Pre-Delivery Checklist 验收：无 emoji 图标、SVG 统一描边、对比度 ≥ 4.5:1、focus-visible、reduced-motion、明暗无闪烁、每个 animation 有 @keyframes、令牌无硬编码 hex、组件不硬编码文案（设计默认值只在 `brand.ts`，运行时覆盖见 §13.5）。

### 13.5 后台可改品牌信息与单一事实来源的协调

用户明确要求 Logo 等可见信息后台可改，因此对模板「品牌文案只存在 `brand.ts`」做有记录的扩展：

- `brand.ts` 保存**设计默认值**（名称、slogan、描述、Logo 引用），首次启动时作为种子写入 `site_settings`
- 运行时以 `site_settings` 为事实来源：后台修改后立即生效；清空某项则回退 `brand.ts` 默认
- 令牌（颜色/阴影/动效）仍只存在 `index.css`，后台不可改；Logo/favicon 上传后存 `data/uploads/`，`site_settings` 只存引用路径
- 该扩展的意图与理由写入 `design-system/lipanel/BRAND.md` 治理章节，保持文档与代码同步
