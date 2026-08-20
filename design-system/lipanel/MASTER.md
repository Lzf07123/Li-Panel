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

2026-08-20 首版交付实测（V1.2 1:1 复刻时代）：

- 后端：pytest 35 passed（认证/SSO/可见性/隔离/站点设置）
- 前端：`tsc -b` + `vite build` 通过（参考实现构建链，含 precompress）
- 容器：`docker stats` 实测内存 46.09MiB、CPU 0.21%、2 个进程（目标 50–90MB，达标）
- 端到端：初始化管理员 → 登录 → 建分组/链接 → 访客面板（私密不可见、URL 隐藏）→ `/go/{id}` 302 跳转 全部通过
- 加速源：`IMAGE_REGISTRY=docker.m.daocloud.io/library` 完成镜像构建验证
