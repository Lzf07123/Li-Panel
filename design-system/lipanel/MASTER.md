# Li&Panel 实现速览（MASTER.md）

日期：2026-08-20 ｜ 版本：V1.4（与 Li-Design 子模块对齐）

## 令牌（事实来源：`frontend/src/index.css`，前缀 `lipanel`）

- 令牌前缀：`lipanel`（从 Li-Design `reusable-tokens.template.css` V1.4 实例化，仅槽位差）
- 浅色：bg `#f6fbf9`、surface `#ffffff`、surface-2 `#eef6f3`、fg `#35423f`、muted `#64736c`、border `#e1ece8`、primary `#25786d`、ring `#25786d`
- 浅色语义色：success `#2a7c52` / warning `#9a5c05` / destructive `#c43737`（V1.3 AA 调校值）
- 深色：bg `#3a3f45`、surface `#434950`、surface-2 `#4b5259`、fg `#f0f2f4`、muted `#b8c0c7`、border `#545c64`、primary `#7fd4c6`、ring `#7fd4c6`
- 深色软底带文字组件回退 `*-soft-solid` + `*-soft-fg`（primary `#d9f4ee/#17332e`、success `#e3f6e9/#14532d`、warning `#fdf3d8/#78350f`、destructive `#fdeeee/#7f1d1d`）
- 按钮：半透明单色（浅 10%/深 13%）+ 细描边 + `::after` 扫光
- 阴影：`--shadow-sm/md/lg` 水绿 tint，透明度总和 < 0.1
- 动效：`--motion-fast/base/slow = 150/250/350ms`；只动 transform/opacity/background-position
- 科技光效：网格 12s、光束 10s（错峰 0.8/4.2/7.5s）、光点 6s；极光四斑 18/22/28/24s；`prefers-reduced-motion` 单帧

## 组件清单

- 组件按 Li-Design 模板 V1.4 实例化，令牌统一为 `--lipanel-*`：`AuthShell`/`AppHeader`/`AsyncButton`/`PasswordInput`/`Notice`/`Modal`/`ConfirmDialog`/`ToastProvider`/`ScrollTabs`/`PillTabs`/`MagicBento`/`StrokeText`/`SiteFooter`/`ThemeToggle`/`PageSkeleton`/`AuthSkeleton`/`GuestOnly`/`Brand` 及 `bits/*`（Aurora/BlurText/CountUp/FadeIn/LineIcon/ShinyText/StatusIcon/TechAmbience）
- 随模板补全 V1.4 UI 控件：`.select`/`.select-sm`、`.custom-select-*`、`.dropdown-menu`、`.suggest-menu`、`.avatar`、复选/单选/文件按钮、`.pagination`、`.breadcrumb`、`.progress`、`.table-empty-row`
- 氛围：`FloatingBackground`（Canvas + `useFloatingBackground`，参考实现逐字一致）、`AuroraBackground`、`TechAmbience`
- 主题：`useTheme` + `ThemeToggle` 读写 `lipanel-theme`，切换 `html.dark`；旧 `portal-theme` 仅作迁移回退

## 响应式

- 断点：375 / 768 / 1024 / 1440；面板网格 1→2→3→4 列
- 顶栏移动端文字隐藏；管理标签横滑（`ScrollTabs`）；表格 `overflow-x-auto` 横向滚动
- 移动端氛围减量与 `prefers-reduced-motion` 均由参考实现 `index.css` 统一处理

## 页面模式

| 页面 | 外壳 | 氛围浓度 |
| --- | --- | --- |
| `/setup`、`/login`、`/sso/link` | AuthShell（`max-w-md` 居中卡 + 品牌 + 备案） | 默认（10 + TechAmbience） |
| `/` 面板 | AppHeader + `max-w-7xl` 内容 | 10（soft） |
| `/settings` 管理 | AppHeader + 表单/卡片 | 4×0.5 |

## 修复记录

2026-08-21 上线前审查修复：

- SPA 回退路径穿越（编码 `..` 下载任意文件）与通知 webhook 公开泄漏已修复；登录锁定窗口到期自动解除；SSO 回调/登出改用配置的会话 Cookie 名，`PANEL_HOST_COOKIE` 全链路生效；登出回跳拒绝反斜杠。
- compose 补齐全部运行期环境变量透传（此前 Host 白名单/HSTS/登录锁定参数等在容器内失效）；后端固定监听容器内 8000，`PANEL_PORT` 仅宿主机对外端口；`npm ci --registry` 修复 `NPM_REGISTRY` 被 `frontend/.npmrc` 覆盖；VITE_* 品牌参数接入 Docker 构建；nginx 补 `text/javascript` gzip 类型并开 `gzip_static`/`gzip_vary`。
- 验证：pytest 177 passed、vitest 13 passed、容器实测 46.66MiB、冒烟 PASS。

2026-08-21 健康结果显示与 favicon 自动获取：

- 卡片健康结果统一右侧对齐并显示延迟毫秒（`min-w-14` + `text-right` + `tabular-nums`，在线显示 `Nms`、离线/未知显示状态文案，点击状态点仍可看趋势）
- 新建/编辑快捷方式时自动后台抓取站点 favicon（`BackgroundTasks`，受控出站与缓存复用，失败静默；自定义图标不覆盖；`PANEL_LINK_ICON_FETCH` 可关）；管理页新增「补抓缺失图标」批量按钮；保存后延迟刷新以显示新图标
- 验证：pytest 156 passed；Playwright 端到端——新建链接自动生成 `/favicons/link-*` 图标、卡片右侧统一右对齐延迟文本

2026-08-21 图标识别增强与延迟显示微调：

- 图标抓取识别增强（`backend/app/favicon.py`）：HTMLParser 解析全部 `<link>` 候选（icon/shortcut icon/apple-touch-icon 等含 icon 的 rel）、按 `sizes` 择优（上限 512，同分优先 apple-touch-icon）、支持 `<base href>`、data: URI 内联图标、无 link 时回退源站 `/favicon.ico`、支持 SVG 并按真实 Content-Type 保存正确扩展名
- 延迟显示紧贴状态点：状态点与延迟文本间距统一 4px，文本左对齐紧邻圆点（`min-w-12` + `tabular-nums` 保持各卡片对齐）
- 验证：pytest 163 passed（新增 7 项识别测试：回退/择优/base/data URI/apple-touch/SVG）；Playwright 端到端——延迟间隙 4px 一致、自动抓取生成 `/favicons/link-*`

2026-08-21 图标识别增强（第二轮，覆盖全部常见类型）：

- `<link rel="manifest">`：解析 Web App Manifest `icons[]`（purpose any 优先于 maskable、sizes 择优，512KB 上限）
- `<meta>` 图标：`msapplication-TileImage`、`og:image`、`twitter:image` / `twitter:image:src`
- 根目录回退链：`/favicon.ico` → `/favicon.png` → `/favicon.svg`
- 内联 data: URI：base64（png/jpeg/webp/svg/x-icon）+ 非 base64 内联 SVG
- 评分改为 sizes 优先（512 图标胜过 180 apple-touch）、apple-touch 次之；候选按优先级链尝试（深度上限 3）
- 验证：pytest 170 passed（favicon 22 项，新增 manifest/og/msapplication/根目录 png/内联 SVG/评分）；Playwright 端到端 manifest 自动抓取通过

2026-08-21 消息弹窗完善与 nginx 反代编排：

- 消息弹窗新增 `loading` 通知类型（旋转图标、默认常驻由调用方关闭）；默认标题与「关闭通知」接入 i18n；最大堆叠 5 条自动裁剪；hover 暂停进度已有，补齐 loading 样式
- 编排改为 nginx 反代：`nginx/nginx.conf` 监听 80 反代 `lipanel:8000`，compose 仅 `lipanel-nginx` 发布 `PANEL_PORT:80`，后端真实端口不再映射到宿主机；代理头/上传上限 10m/gzip；README 增补反代说明
- 验证：`docker compose up` 后 `curl localhost:8000/api/health` 返回 ok；`docker ps` 仅 nginx 发布端口；SPA 经反代 200

2026-08-21 页脚备案信息完善：

- ICP / 公安备案条目独立组件（`FilingLink`）：配置了 `VITE_ICP_FILING_TEXT` / `VITE_POLICE_FILING_TEXT` 才显示，链接指向工信部/网安备案官网，条目间用 `·` 分隔
- 备案图标预留占位：图标路径缺失或加载失败时显示「备 / 公」字形方块（`.filing-icon-placeholder`），不再出现破图
- `.env.example` 补充前端备案变量（VITE_ICP_*/VITE_POLICE_*）；Playwright 验证：缺失图标→占位「备」、真实图标正常渲染、链接/标题正确

2026-08-21 备案信息接入后台配置（运行时同步）：

- `site_settings` 新增 `icp_url/icp_icon/police_text/police_url/police_icon`（默认值见 `brand_defaults.py`）；设置页「站点信息」新增备案链接/图标、公安备案号/链接/图标字段
- 页脚改为运行时读取 `/api/panel` 下发的 `site` 配置（`SiteFooter site` 属性），未提供时回退 `brand.ts` 默认值；`footer_text` 同步展示
- 验证：pytest 171 passed；Playwright 端到端——后台写入备案 → 页脚立即显示；设置页修改公安备案号 → 保存后面板页脚同步新值

2026-08-21 个人设置组件比例统一：

- 输入/选择组件高度统一（语言/主题/链接模式 select 与 RSS 订阅输入同为 ~41px）
- 按钮统一 h-8（32px）：会话吊销、快照恢复等不再混用 h-7/h-8
- 版式与其他设置页一致：个人设置改为全宽卡片（960px，`p-6 sm:p-8`），语言/主题/链接模式三列网格，子卡片全宽；验证：桌面卡片 960px、select 287px/41px、子卡片 894px；移动端 375 无溢出

2026-08-21 面板重复分组与健康检测触发修复：

- 备份导入/恢复按分组名（大小写不敏感）合并复用，不再创建同名重复分组；链接仍按追加语义进入对应分组（`backend/app/routers/backup.py`）
- 健康检测由用户侧发起：首次进入面板与回到面板（标签页可见性恢复 / 窗口聚焦 / 从其他页返回）时以 `?refresh=1` 强制重新检测，忽略服务端 60s 缓存（`backend/app/routers/health.py`、`frontend/src/pages/PanelPage.tsx`）
- 验证：pytest 153 passed；Playwright 端到端——备份导入两次后分组仍为 2（无重复）、面板加载与 focus 事件均触发 `?refresh=1` 检测

## 验收状态

2026-08-20 端口变量化重建实测：

- `PANEL_PORT`（默认 8000）已贯通 Dockerfile（EXPOSE/HEALTHCHECK/CMD）、compose（build.args/environment/ports）、`.env.example` 与设计文档 §11
- `docker compose build` 成功 → `docker compose up -d` → `curl -fsS http://localhost:8000/api/health` 返回 `{"status":"ok"}`
- `docker compose ps`：`Up (healthy)`，`0.0.0.0:8000->8000/tcp`；`docker stats`：内存 46.01MiB / CPU 0.24% / 3 进程（仍 ≤90MB 目标）
- 覆盖验证：`PANEL_PORT=8080 docker compose config` 解析为 `published: 8080` / `target: 8080`，环境变量同步注入

2026-08-20 Phase A（V01–V10）实测：

- 前端：`npx tsc --noEmit && npx vite build` 通过；V01–V10 每版独立提交于 `codex/50-iterations`，路线图见 `docs/superpowers/plans/2026-08-20-lipanel-50-iterations.md`
- 后端：pytest 35 passed（V07 增加 `frame-src 'self' https: http:` 后回归通过）
- 新增能力：`/` 聚焦搜索与 `Esc` 清空；`↑/↓/Home/End/Enter` 键盘导航；无结果外部搜索回退；标签编辑与筛选；最近使用（`lipanel-recent`）；`Ctrl/⌘+K` 命令面板；内置窗口打开（iframe 沙箱 + 新标签兜底，CSP 已记录到设计文档 §9）；分组折叠记忆（`lipanel-collapsed-groups`）；空状态引导；跳过导航链接与 `main#content` 可达性
- 顺带修复：切换可见性时不再重置 url_wan/description/tags/group_id/open_mode（V07）；搜索结果计数按筛选后计算（V03）

2026-08-20 V1.4 对齐实测：

- 前端：`npx tsc --noEmit && npx vite build` 通过，产物 CSS 含 `--lipanel-*` 令牌与 V1.4 控件类，无 `--portal-*` 残留
- 后端：pytest 35 passed（视觉改动不涉及后端，回归通过）
- 一致性：模板占位符清零；`--lipanel-*` 令牌集合与模板一致；每个 `animation` 均有 `@keyframes`；浅色语义色为 V1.3 AA 调校值
- 主题：存储键迁移为 `lipanel-theme`，旧 `portal-theme` 仅作一次性回退
- 容器：重建 `lipanel:local` 并 `docker compose up -d` 后 health 返回 `{"status":"ok"}`，`docker stats` 实测 45.73MiB / CPU 0.23% / 2 进程
- 视觉对照：四档响应式与对比度建议在浏览器中人工复核

2026-08-21 前端显示优化实测（`codex/frontend-display`）：

- 面板问候 + 日期/时间小组件：`DateTimeWidget` 本地时区秒级更新，登录显示「晚上好，用户名」，访客显示通用问候；移动端 375px 不溢出（路线图 V24 时钟、V25 问候前端部分）
- 快捷方式卡片长标题两行显示：`line-clamp-2` + `title` 悬停提示，长名称不再单行截断
- 面板分区标题显示数量：分组/未分组/最近使用标题后显示链接数
- 设置页表格窄屏优化：名称列 `min-w` 保证可读，移动端 `overflow-x-auto` 横向滚动；操作列 `whitespace-nowrap` 防换行
- 验证：`npx tsc --noEmit && npx vite build` 通过；后端 pytest 35 passed（无后端改动）；Playwright 实测时钟每秒跳动、长标题两行完整显示、四档视口无横向溢出、无断图、对比度无低值

2026-08-21 Phase B（V11–V20）实测：

- V11 链接拖拽排序：`PATCH /api/links/order`（提供 id 前置整体重排，重复 400 / 跨用户 404）；面板卡片 HTML5 组内拖拽，跨分组提示「仅同组生效」，保存失败回滚；`npx tsc --noEmit && npx vite build` 通过，pytest 40 passed，Playwright 组内拖拽端到端（PATCH 200 + 顺序持久化）通过
- V12 分组拖拽排序：`PATCH /api/groups/order`（同 V11 整体重排语义）；管理页分组表拖拽行高亮；pytest 45 passed，Playwright 拖拽 常用→娱乐 后顺序持久化
- V13 分组图标与配色：新增 `GroupIcon`（10 个内置线框图标，零外部依赖/不破坏 CSP）；管理页创建表单与表格行内图标选择，切换可见性不丢 icon；面板与访客视图分组标题显示稳定色相图标瓦片（无图标回退首字母）；pytest 48 passed，Playwright 设置→面板/访客显示通过
- V14 链接图标自动抓取：新增 `app/favicon.py` 受控出站模块（`PANEL_LINK_ICON_FETCH`、5s 超时、BoundedSemaphore(4)、60s 内存缓存、1MB 上限、png/jpeg/webp/ico 白名单、HTML `<link rel=icon>` 解析与 `/favicon.ico` 回退、仅 http/https）；`POST /api/links/{id}/fetch-icon` 写回 `icon_type=upload`；`/favicons/{name}` 文件名正则白名单 + SPA fallback 排除；管理页「抓图标」按钮；pytest 53 passed（本地 fixture 服务器），Playwright 端到端通过
- V15 批量操作：`POST /api/links/batch-delete|batch-move|batch-visibility`（全量 user_id 校验、空列表 422、目标分组归属校验）；管理页链接表复选框 + 全选 + 批量操作栏（删除/移动/公开/私密）与确认弹窗；pytest 59 passed，Playwright 批量设公开端到端通过
- V16 标签管理页：`GET /api/tags`（按用户统计）、`PUT/DELETE /api/tags/{tag}`（重命名全量更新去重保序、删除；URL 编码中文标签；跨用户隔离）；设置页新增「标签管理」标签页（计数、行内重命名、删除确认）；pytest 65 passed，Playwright 重命名端到端通过
- V17 重复检测：创建/编辑同名（NOCASE）或同 `url_lan` 返回 409 `{code:"duplicate", message}`（排除自身、`force:true` 强制保存）；前端 API 客户端解析结构化 detail，表单显示「已存在…」提示 + 「仍要保存」；pytest 70 passed，Playwright 409→强制保存端到端通过
- V18 JSON 备份导出/导入：`GET /api/backup`（本人分组/链接/设置，管理员含 site_settings）；`POST /api/backup` 结构+URL 校验后追加导入（新 id 映射、设置 upsert、管理员站点设置 upsert）；个人设置页「数据备份」卡片（导出下载、JSON 文件导入）；pytest 76 passed，Playwright 导出→导入追加端到端通过
- V19 自动快照备份：`app/snapshot.py` 在 `get_db` 提交后按 `conn.total_changes` 精确检测数据变更，写 `data/backups/snapshot-{ts}.json`（全量 groups/links/settings/site_settings），`PANEL_BACKUP_KEEP` 滚动清理；登录/只读不写；pytest 79 passed
- V20 恢复向导：`GET /api/backup/snapshots`（管理员，快照预览条数）、`POST /api/backup/restore/{name}`（文件名白名单、快照行按 user_id 过滤后追加导入、管理员含 site_settings）；个人设置页自动快照列表 + 恢复确认弹窗；pytest 83 passed，Playwright 快照列表→恢复→追加导入端到端通过
- V21 链接健康检查引擎：`app/health.py` 受控出站（`PANEL_HEALTH_CHECK`、HEAD 优先 405/501 回退 GET、5s 超时、BoundedSemaphore(4)、60s 缓存、<500 up）；`GET /api/health/links` 仅返回本人链接状态；pytest 89 passed（本地 fixture up/down/缓存/关闭/隔离）
- V22 卡片状态点：`.status-dot-up/down` 语义色（复用 success/destructive 令牌）；`LinkCard` 状态点 + hover 毫秒 title；健康检查改为 ThreadPoolExecutor≤4 并发（面板秒级返回）；`connect(..., timeout=10)` + `PRAGMA busy_timeout=10000`；pytest 89 passed，Playwright 44 链接状态点全部渲染
- V23 状态历史：`link_health` 表（每链接 10 分钟采样、24h/144 条滚动清理、跨用户隔离）；`GET /api/health/links/{id}/history`（404 防越权）；`HealthTrendModal` 趋势条弹层（绿/红 + 图例）；pytest 93 passed，Playwright 点状态点弹历史弹层通过
- V24 时钟小组件：`DateTimeWidget` 本地时区秒级更新（路线图验收回填，实现于 `codex/frontend-display`）
- V25 问候与「今天」常用入口：时间段问候（登录显示用户名）+ 当天打开快捷方式 chips（无当天记录回退最近使用）；Playwright 验证 chips 渲染
- V26 RSS/ATOM 小组件：`app/rss.py`（≤3 源、8s 超时、并发 ≤3、10min 缓存、标准库 XML）；`rss_feeds` 用户设置（校验/上限）；`GET /api/rss`；个人设置页订阅管理、面板「订阅」折叠卡片；SQLite 改自动提交（`isolation_level=None`）+ `busy_timeout` 根治锁冲突；pytest 98 passed，Playwright 端到端通过
- V27 公开状态页：`GET /api/health/status`（无鉴权但遵循 public_mode，仅 is_public 链接、健康检查复用并发/缓存）；访客面板状态点；pytest 100 passed，Playwright 访客 28 个公开链接状态点通过
- V28 通知通道：`app/notify.py`（httpx POST 5s 超时、失败静默）；site_settings `notify_url/notify_enabled`（默认空/关，URL 校验）；`_record_samples` 采样时状态变化即通知（首次采样视为变化）；站点信息页通知设置卡片；pytest 103 passed（fixture：变化/同状态/关闭/失败忽略）
- V29 检测配置中心：links 列 `health_enabled/health_interval/health_timeout/health_threshold`（SCHEMA + ALTER 迁移 + 备份导入携带）；健康引擎按链接配置执行（开关排除、自身间隔/超时、连续失败阈值 `fail_count`）；管理页链接表单健康检查配置组；pytest 106 passed
- V30 状态导出 API：`GET /api/health/export?format=csv|json`（仅本人启用检测链接，CSV 含表头）；pytest 110 passed
- V31 SSO 解绑：`GET /api/sso/status`、`DELETE /api/sso/identity`（本地密码确认、错密 403、未绑定 400、解绑不删本地账号）；个人设置页解绑弹窗；pytest 114 passed
- V32 RP 发起登出：`GET /auth/sso/logout`（本地注销 + OIDC 发现 `end_session_endpoint` + `id_token_hint` + `post_logout_redirect_uri` 白名单 `PANEL_SSO_LOGOUT_REDIRECTS`）；sessions 新增 `sso_id_token`（ALTER 迁移）；pytest 117 passed
- V33 回程登出：`POST /auth/sso/backchannel`（JSON/form 双格式；`OIDCClient.validate_logout_token` 验签 + iss/aud/exp/events；按 sessions.sso_sid + sso_identities.subject 精确删除，幂等）；pytest 123 passed
- V34 Host 白名单：`PANEL_ALLOWED_HOSTS`（精确/`*.` 通配，为空放行）；security 中间件先校验 Host；pytest 126 passed
- V35 登录锁定：`LoginLockout`（用户名+IP，`PANEL_LOGIN_MAX_FAILS`/`PANEL_LOGIN_LOCK_MINUTES`，成功重置，未知用户同行为）；登录接口 429；pytest 130 passed
- V36 角色与权限：site_settings 写接口 admin-only（403），读公开；前端按角色过滤「站点信息」标签页；pytest 133 passed
- V37 会话管理：`GET /api/sessions`（current 标记）、`DELETE /api/sessions/{id}`（当前拒绝 400、跨用户 404）、`DELETE /api/sessions`（吊销其他）；个人设置页会话卡片；pytest 138 passed
- V38 审计日志：`audit_logs` 表 + `app/audit.py`（登录/登出/SSO 绑定解绑/备份恢复/站点设置变更，滚动 1000 条）；`GET /api/audit-logs` admin-only；pytest 142 passed
- V39 安全响应头：CSP `font-src`、COOP/CORP same-origin、Permissions-Policy、HSTS 可配；pytest 144 passed
- V40 密钥与上传加固：`PANEL_HOST_COOKIE`（`__Host-` 前缀，cookie 名全链路变量化）；上传魔数校验；生产 secret ≥32 启动校验；pytest 148 passed
- V41 PWA 清单：`manifest.json`（standalone、主题色、512 maskable/any）、application-name、apple-touch-icon；构建产物含清单
- V42 离线缓存外壳：`public/sw.js`（静态缓存优先、导航网络优先+离线回退、API 不缓存、版本化缓存清理）；生产注册；构建产物含 sw.js
- V43/V44 i18n 与语言偏好：`lib/i18n.ts` + `locales/en-US.ts`（中文原文即 key、插值、useI18n）；主要页面迁移；语言选择双持久化（localStorage + 后端 `lang`）；pytest 149 passed，Playwright 英文界面通过
- V45/V46 缓存与版本：`/assets/*` immutable 长期缓存、`X-Panel-Version`、`/api/health.version`、页脚版本、CHANGELOG
- V47/V48 文档与前端测试：README 部署加固；vitest 13 passed（lib 层）
- V49/V50 冒烟与性能：`scripts/smoke.sh` 全流程 PASS；`scripts/check-size.sh` 0.52MB 达标；pytest 151 passed；容器实测 46.5MiB / 3 进程

2026-08-20 首版交付实测（V1.2 1:1 复刻时代）：

- 后端：pytest 35 passed（认证/SSO/可见性/隔离/站点设置）
- 前端：`tsc -b` + `vite build` 通过（参考实现构建链，含 precompress）
- 容器：`docker stats` 实测内存 46.09MiB、CPU 0.21%、2 个进程（目标 50–90MB，达标）
- 端到端：初始化管理员 → 登录 → 建分组/链接 → 访客面板（私密不可见、URL 隐藏）→ `/go/{id}` 302 跳转 全部通过
- 加速源：`IMAGE_REGISTRY=docker.m.daocloud.io/library` 完成镜像构建验证
