# Li&Panel 50 版本迭代路线图

日期：2026-08-20

状态：V01–V10（Phase A）已完成；V11–V50 待执行

目标：对照主流面板项目（Sun-Panel / Dashy / Homepage / Homarr / Glance / Heimdall / Homer / Uptime Kuma），吸取可复用经验，在不破坏项目宪法（FastAPI + SQLite + React 技术栈、50–90MB 低占用、服务端可见性过滤、OIDC 全量校验、令牌只在 `index.css`）的前提下，自行迭代 50 个可独立验收的版本。

## 1. 调研结论：主流面板项目对比

调研时间 2026-08-20，来源包括各项目官网/仓库与 2026 年社区对比研究：

- [Dashy 官网](https://dashy.to/)
- [Homarr 仓库](https://github.com/homarr-labs/homarr)
- [Homepage 仓库](https://github.com/gethomepage/homepage)
- [Glance](https://github.com/glanceapp/glance)
- [Sun-Panel 仓库](https://github.com/Mydong/sun-panel)
- [Homarr vs Dashy 对比](https://selfhosting.sh/compare/homarr-vs-dashy/)
- [2026 自托管面板深度盘点](https://www.youngju.dev/blog/culture/2026-05-16-self-hosted-dashboards-start-pages-2026-homepage-homarr-heimdall-dashy-glance-olivetin-flame-sui-deep-dive.en)
- [2026 面板选型评分板](https://laoujin.github.io/Atlas/research/2026-06-06-stay-or-migrate-homelab-dashboard-decision-2026/views/scoreboard.html)

| 项目 | 定位 | 值得吸收的经验 | 不吸收 / 调整理由 |
| --- | --- | --- | --- |
| Sun-Panel（本项目参考） | NAS 导航面板 | 一键内外网切换（已有）；丰富图标（文字+SVG+图标库）；网页内置小窗口打开 | 保持现有 DB + 后台可改模型 |
| Dashy | 可定制仪表盘 | 卡片状态点（HTTP 状态检测）；`/` 即时搜索 + 快捷键；多种启动方式（新标签/弹窗/工作区）；PWA 可安装；多语言；50+ 主题/自定义 CSS | 不做 50 套主题；CSS 变量定制仅保留现有令牌体系 |
| Homepage | YAML 配置即代码仪表盘 | 服务健康轮询；配置可版本化（备份/导出）；`HOMEPAGE_ALLOWED_HOSTS` Host 白名单教训；版本钉扎教训 | 不把 YAML 变成主配置（与「后台可改」冲突）；不引入 Docker socket 自动发现 |
| Homarr | GUI 拖拽仪表盘 | 拖拽排序；OIDC/LDAP + RBAC；多板隔离；内置 ping/监控；时间序列图 | RBAC 与多板放远期；不引入 Redis/WebSocket 实时层 |
| Glance | 数据流首页 | 轻量单二进制；RSS/天气/自定义 API 小组件；移动端网格 | 不做 Go 重写；小组件只做低占用子集 |
| Heimdall | 极简启动页 | 顶部搜索 + 外部搜索引擎回退；极简卡片 | 增强应用（Sonarr/Plex 等）超出个人快捷方式面板定位 |
| Homer | 静态 YAML 启动页 | connectivity check 状态指示；搜索过滤 | 无后端模型不适合本项目 |
| Uptime Kuma | 可用性监控 | 健康检查 + 通知通道；备份恢复；REST API | 不引入完整监控系统，只做「链接级轻量检测」 |
| OliveTin | 动作面板 | 动作按钮 + 参数白名单 | 远期可选，非当前主方向 |

## 2. 吸收原则（在项目宪法约束下的取舍）

1. **技术栈与资源目标不动摇**：React + TS + Vite + Tailwind CSS 4、FastAPI + SQLite、50–90MB 内存目标。任何新功能先过「低占用审计」：缓存、限并发、可开关。
2. **DB 驱动 + 后台可改是既定事实**：借鉴 Homepage 的「配置即代码」只落实为 JSON 备份导出/导入、自动快照与恢复向导，不引入 YAML 主配置。
3. **安全边界不变**：私密字段服务端过滤、公开链接 `/go/{id}` 隐藏原始地址、OIDC `state/nonce/at_hash/iss/aud` 全量校验、跨用户 id 一律 404。
4. **新增外部请求一律受控**：状态检测、RSS、favicon 抓取等出站请求必须：可配置开关、超时、内存缓存、并发上限，且只作用于登录用户自己的数据。
5. **视觉与文案纪律**：颜色/动效令牌只在 `frontend/src/index.css`；品牌默认文案只在 `brand.ts`；组件 UI 文案在 V43 i18n 版本统一抽取。
6. **每版本独立可回滚**：一个版本一个提交，验收通过才合入；版本间尽量无跨版本耦合，保证可以单独 cherry-pick / revert。

## 3. 50 版本路线图

### Phase A：搜索与导航体验（V01–V10）

借鉴：Dashy（搜索/快捷键/启动方式）、Heimdall（外部搜索）、Homer（搜索过滤）、Sun-Panel（小窗打开）。

| 版本 | 名称 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| V01 | 搜索快捷键与结果计数 | `/` 聚焦搜索框、`Esc` 清空/失焦；显示 `kbd /` 提示；结果计数随查询变化 | 按 `/` 聚焦；`Esc` 清空；计数正确；`tsc`/`vite build` 通过 |
| V02 | 键盘导航结果 | 搜索框内 `↑/↓` 移动卡片焦点、`Enter` 打开、`Home/End` 首尾 | 焦点随箭头移动且可见；Enter 打开正确地址 |
| V03 | 无结果提示与外部搜索 | 无匹配时展示空态卡片 + Google/Bing 外部搜索入口 | 输入无匹配关键词出现外部搜索按钮，链接正确 |
| V04 | 标签编辑与筛选 | 快捷方式表单支持标签输入（逗号分隔、去重、上限）；面板按标签 chip 筛选 | 建带标签链接；chip 点击筛选；`aria-pressed` 正确 |
| V05 | 最近使用 | 点击卡片记录 `lipanel-recent`（最多 8 条）；面板顶部「最近使用」区，可清空 | 点击后刷新出现最近区；清空生效；访客/登录均可用 |
| V06 | Ctrl+K 命令面板 | 全局 `Ctrl/Cmd+K` 打开命令面板：搜索快捷方式 + 管理/主题/退出等动作，键盘导航 | 面板可开合；Enter 打开结果；Esc 关闭 |
| V07 | 内置窗口打开方式 | `open_mode=modal` 真正生效：链接表单增加「打开方式」；卡片点击弹窗内嵌 iframe（沙箱 + no-referrer），附「新标签打开」兜底；CSP 增加 `frame-src` | pytest 通过（CSP 头含 `frame-src`）；tsc/build 通过；modal 链接弹窗正常 |
| V08 | 分组折叠记忆 | 分组标题可折叠/展开，状态存 `lipanel-collapsed-groups`；搜索时自动展开 | 折叠后刷新保持；搜索时结果不受折叠影响 |
| V09 | 空状态引导 | 无任何快捷方式时展示引导卡：登录用户引导去管理页，访客引导登录 | 全新安装下空态可见，按钮跳转正确 |
| V10 | 可达性补强 | 跳过导航链接；`main#content`；搜索/面板/弹窗 aria 属性；焦点可见性复核 | Tab 首个焦点为跳过链接；tsc/build 通过 |

### Phase B：排序、图标与数据管理（V11–V20）

借鉴：Homarr（拖拽 GUI）、Dashy（图标自动抓取）、Uptime Kuma（备份恢复）、Homepage（配置可版本化）。

| 版本 | 名称 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| V11 | 链接拖拽排序 | 后端 `PATCH /api/links/order`（整组顺序写入，user_id 校验）+ 面板卡片 HTML5 拖拽 | pytest 覆盖跨用户 404；拖拽后顺序持久化 |
| V12 | 分组拖拽排序 | 后端 `PATCH /api/groups/order` + 管理页拖拽 | 同上 |
| V13 | 分组图标与配色 | 分组图标（内置 symbol/iconify/上传）+ 稳定色相 | 分组图标保存并在面板/管理页显示 |
| V14 | 链接图标自动抓取 | 后端抓取站点 favicon（限时/缓存/白名单扩展名），卡片可选使用；不上传则存缓存目录 | 测试用本地 fixture 验证抓取与失败回退 |
| V15 | 批量操作 | 管理页多选：批量删除/移动分组/切换可见性 | 后端批量接口 + pytest；前端确认弹窗 |
| V16 | 标签管理页 | 标签统计、重命名（全量更新）、删除 | 重命名/删除后面板筛选同步 |
| V17 | 重复检测 | 创建/编辑时检测同名或同 URL，前端提示 + 后端 409（可强制保存） | pytest 覆盖 409 语义；前端提示可见 |
| V18 | JSON 备份导出/导入 | `GET/POST /api/backup`（groups/links/settings）；设置页下载/上传；导入校验后追加，不破坏现有数据 | pytest 覆盖导出→清空→导入恢复；非法 JSON/URL 拒绝 |
| V19 | 自动快照备份 | 数据变更后写 `data/backups/snapshot-{ts}.json`，保留最近 N 份（默认 10，环境变量可调） | 变更后快照文件出现；超过 N 份自动清理 |
| V20 | 恢复向导 | 设置页从快照列表选择恢复：预览条数 → 确认 → 导入 | 端到端恢复流程；导入后面板数据一致 |

### Phase C：状态、监控与数据感知（V21–V30）

借鉴：Dashy（状态点）、Homepage（服务轮询）、Uptime Kuma（检测/通知/历史）、Glance（信息小组件）。

| 版本 | 名称 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| V21 | 链接健康检查引擎 | `GET /api/health/links`：HEAD/GET、超时 5s、TTL 60s 缓存、并发 ≤4、环境变量开关（默认开）；仅登录用户自己的链接 | pytest 覆盖 up/down/超时/缓存；结果不泄漏他人数据 |
| V22 | 卡片状态点 | 卡片显示 up/down/unknown 状态点 + hover 显示响应时间；可整页刷新 | 状态点渲染正确；接口失败显示 unknown |
| V23 | 状态历史 | 最近 24h 采样（每 10 分钟一轮）存 `link_health` 表，卡片弹层显示简单趋势 | pytest 覆盖采样写入与查询；前端趋势条渲染 |
| V24 | 时钟小组件 | 面板顶部日期/时间小组件（本地时区，秒级更新） | 时间正确；移动端不溢出 |
| V25 | 问候与快捷入口 | 按时间段问候 + 「今天」常用入口（结合最近使用） | 无外部依赖；显示正确 |
| V26 | RSS/ATOM 小组件 | 可选订阅源（每个用户最多 3 个），服务端解析 + 缓存 + 超时；前端卡片列表 | pytest 覆盖解析/失败/缓存；卡片折叠可关闭 |
| V27 | 公开状态页 | 访客可见「公开快捷方式可用性」汇总（仅公开链接状态） | 访客接口不下发私密数据；状态汇总只含公开项 |
| V28 | 通知通道 | 状态变化时发 ntfy/Webhook（URL 存 site_settings，可关闭） | 测试用 mock 验证 POST 载荷；失败不影响主流程 |
| V29 | 检测配置中心 | 每链接检测开关、间隔、超时、阈值；管理页表单 | 配置持久化并生效 |
| V30 | 状态导出 API | `GET /api/health/export`（CSV/JSON，仅本人数据） | pytest 覆盖格式与隔离 |

### Phase D：安全与身份（V31–V40）

借鉴：Dashy/Homarr（认证与权限）、Homepage（Host 白名单）、设计文档 P1/P2 清单。

| 版本 | 名称 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| V31 | SSO 解绑/换绑 | `GET /api/sso/status` + `DELETE /api/sso/identity`（本地密码确认）；个人设置页按钮与确认 | pytest 覆盖密码错误/解绑后状态；解绑不删本地账号 |
| V32 | RP 发起登出 | `GET /auth/sso/logout`：发现文档 `end_session_endpoint` + `id_token_hint` + 回跳白名单（环境变量） | pytest 覆盖白名单校验与失败回退 |
| V33 | 回程登出 | `POST /auth/sso/backchannel`：`logout_token` 验签、`sub`+`sid` 精确下线 | pytest 覆盖合法/伪造/过期 token |
| V34 | Host 白名单 | `PANEL_ALLOWED_HOSTS`（逗号分隔）；非白名单 Host 返回 403；为空则放行 | pytest 覆盖白名单/通配/拒绝 |
| V35 | 登录锁定 | 每用户名+IP 连续失败 5 次锁 15 分钟；限流与锁可配置 | pytest 覆盖锁定/解锁；不泄露用户是否存在 |
| V36 | 角色与权限 | admin/user 角色落地：普通用户不可改 site_settings、不可看管理页站点区；管理页按角色隐藏 | pytest 覆盖角色鉴权；前端路由守卫 |
| V37 | 会话管理 | `GET/DELETE /api/sessions`：查看自己的会话、单点/全部吊销 | pytest 覆盖吊销后 401；UI 展示 |
| V38 | 审计日志 | 登录/登出/SSO 绑定/解绑/备份恢复/站点设置变更写入 `audit_logs`（滚动保留 1000 条，仅 admin 可读） | pytest 覆盖事件写入与 admin 隔离 |
| V39 | 安全响应头补全 | HSTS（可配）、`Cross-Origin-Opener-Policy`、`Cross-Origin-Resource-Policy`、`Permissions-Policy`、CSP `font-src` | pytest 断言头；README 说明 HTTPS 部署要求 |
| V40 | 密钥与上传加固 | Cookie 前缀 `__Host-` 可配；上传校验魔数（不只扩展名）；secret 长度启动校验 | pytest 覆盖魔数拒绝与启动校验 |

### Phase E：体验、部署与治理（V41–V50）

借鉴：Dashy（PWA/多语言）、Homepage（版本钉扎/Host 教训）、Glance（轻量）、Uptime Kuma（运维纪律）。

| 版本 | 名称 | 内容 | 验收标准 |
| --- | --- | --- | --- |
| V41 | PWA 清单与图标 | `manifest.webmanifest`、`theme-color`、apple-touch-icon、`<meta name="application-name">` | Lighthouse/手动检查可安装条件 |
| V42 | 离线缓存外壳 | 轻量 Service Worker：静态资源缓存优先、API 网络优先、版本化更新 | 断网刷新可显示外壳；更新后资源失效 |
| V43 | i18n 框架 | 抽取全部 UI 文案到 `locales/zh-CN.ts`/`en-US.ts`，默认中文 | 切换语言后主要页面文案变化；无硬编码残留（rg 抽查） |
| V44 | 语言偏好 | 站点默认语言 + 用户语言设置 + 浏览器偏好回退 | 设置持久化并生效 |
| V45 | 静态资源长期缓存 | `/assets/*` 加 `Cache-Control: public, max-age=31536000, immutable`；API 保持 no-store；响应头 `X-Panel-Version` | pytest 断言头；构建产物版本化 |
| V46 | 版本信息 | `GET /api/health` 返回 `version`；页脚显示版本；`docs/CHANGELOG.md` 按版本记录 | 版本号与 CHANGELOG 一致 |
| V47 | 部署加固文档 | README 增加：镜像版本钉扎、反代 HTTPS、Host 白名单、备份恢复演练、`PANEL_SECRET_KEY` 轮换 | 文档可照做；示例命令无占位符 |
| V48 | 前端测试补齐 | vitest 覆盖搜索过滤、标签筛选、主题切换、表单校验 | `npm test` 通过 |
| V49 | 端到端冒烟脚本 | `scripts/smoke.sh`：初始化→登录→建分组/链接→可见性→备份导出→恢复 | 脚本在干净数据目录下全绿 |
| V50 | 性能与内存回归 | 构建体积预算脚本；pytest 全套 + `vite build` + `docker stats` 实测回填 MASTER.md 与本文档 | 内存仍 ≤90MB；体积不超预算（记录基线） |

## 4. 执行与验收规则

- 分支：`codex/50-iterations`，每版本一个独立提交，提交消息 `<type>: Vxx 名称`；全部完成后 `--no-ff` 合并回 `main`（保留 merge 记录）。
- 验证命令（按版本实际涉及范围）：`cd backend && python -m pytest -q`；`cd frontend && npx tsc --noEmit && npx vite build`；涉及容器的版本执行 `docker compose build && docker compose up -d && curl -fsS http://localhost:8000/api/health && docker stats --no-stream lipanel`。
- 每完成一版：把本文档状态列打勾，并回填 `design-system/lipanel/MASTER.md` 验收状态；涉及设计文档承诺变更（如 CSP）同步修订设计文档。
- 跨用户数据隔离、可见性过滤、OIDC 校验在任何版本中不得回退；新增外部请求必须可开关、限时、缓存、限并发。

## 5. 状态

- ✅ V01–V10（Phase A）：2026-08-20 完成。提交范围 `c7a2766`（路线图）→ `c3253c7`（V10），每版独立提交；验收输出见 `design-system/lipanel/MASTER.md`。
- ✅ V11（链接拖拽排序）：2026-08-21 完成。`PATCH /api/links/order`（整体重排、跨用户 404、重复 400）+ 面板 HTML5 组内拖拽（跨分组提示、失败回滚）。pytest 40 passed；Playwright 端到端：拖拽后顺序持久化。
- ✅ V12（分组拖拽排序）：2026-08-21 完成。`PATCH /api/groups/order`（同 V11 语义）+ 管理页分组表 HTML5 拖拽。pytest 45 passed；Playwright 端到端：拖拽后顺序持久化。
- ✅ V13（分组图标与配色）：2026-08-21 完成。内置 10 个线框图标（零外部依赖）+ 管理页图标选择 + 面板/访客稳定色相瓦片。pytest 48 passed；Playwright 端到端：图标保存并显示。
- ✅ V14（链接图标自动抓取）：2026-08-21 完成。`POST /api/links/{id}/fetch-icon` 受控抓取（`PANEL_LINK_ICON_FETCH` 开关、5s 超时、并发 ≤4、60s 缓存、≤1MB、类型白名单、HTML icon 解析 + /favicon.ico 回退、SSRF 仅 http/https）；管理页「抓图标」按钮；`/favicons/{name}` 严格文件名白名单。pytest 53 passed；本地 fixture + Playwright 端到端通过。
- ✅ V15（批量操作）：2026-08-21 完成。`batch-delete/move/visibility` 三接口（全量 user_id 校验、空列表 422）+ 管理页链接表多选、全选、批量操作栏与确认弹窗。pytest 59 passed；Playwright 端到端：勾选 2 项批量设公开成功。
- ✅ V16（标签管理页）：2026-08-21 完成。`GET /api/tags` 统计、`PUT/DELETE /api/tags/{tag}` 重命名/删除（全量更新、去重保序、用户隔离、URL 编码中文标签）；管理页「标签管理」标签页（列表/计数/行内重命名/删除确认）。pytest 65 passed；Playwright 端到端：重命名 代码→工程 成功。
- ✅ V17（重复检测）：2026-08-21 完成。创建/编辑同名或同 URL 返回 409（结构化 `{code,message}`，忽略自身、大小写不敏感），`force=true` 可强制保存；前端表单显示提示 + 「仍要保存」。pytest 70 passed；Playwright 端到端：409 → 提示 → 强制保存 201。
- ✅ V18（JSON 备份导出/导入）：2026-08-21 完成。`GET/POST /api/backup`（分组/链接/个人设置；管理员含站点设置；导入校验 URL/结构后追加，不删除现有数据）；个人设置页「数据备份」导出下载/导入合并。pytest 76 passed；Playwright 端到端：导出 3 组/11 链接 → 导入后 6 组/22 链接。
- ✅ V19（自动快照备份）：2026-08-21 完成。数据接口提交后（`total_changes` 精确检测）写 `data/backups/snapshot-*.json`，`PANEL_BACKUP_KEEP`（默认 10）滚动清理；登录等非数据请求不写。pytest 79 passed。
- ✅ V20（恢复向导）：2026-08-21 完成。`GET /api/backup/snapshots` 预览条数（管理员）、`POST /api/backup/restore/{name}` 快照追加恢复（文件名白名单、按 user_id 过滤、管理员含站点设置）；个人设置页快照列表 + 确认弹窗。pytest 83 passed；Playwright 端到端：快照列表 → 恢复 → 链接 22→44。
- ✅ Phase B（V11–V20）全部完成：2026-08-21，提交范围 `6f01ab3`（V11）→ `3313a50`（V20）。
- ✅ V21（链接健康检查引擎）：2026-08-21 完成。`GET /api/health/links` 受控检查（`PANEL_HEALTH_CHECK` 开关、HEAD 优先 405/501 回退 GET、5s 超时、并发 ≤4、60s 缓存、<500 视为 up）；仅本人链接。pytest 89 passed（本地 fixture：up/down/缓存/关闭/隔离）。
- ✅ V22（卡片状态点）：2026-08-21 完成。面板卡片状态点（up 绿 / down 红 / unknown 灰），hover 显示响应毫秒；健康检查并发化（ThreadPoolExecutor≤4）；SQLite `busy_timeout=10s` 硬化。pytest 89 passed；Playwright 端到端：44 个链接状态点全部渲染（在线/离线）。
- ✅ V23（状态历史）：2026-08-21 完成。`link_health` 表（10 分钟采样、24h/144 条滚动清理）+ `GET /api/health/links/{id}/history`；卡片状态点点击弹趋势条（绿/红 + 图例）。pytest 93 passed；Playwright 端到端：点状态点弹出历史弹层。
- ✅ V24（时钟小组件）：2026-08-21 完成（前端显示优化分支 `codex/frontend-display` 先行落地，`DateTimeWidget` 本地时区秒级更新，375px 不溢出；此处回填验收状态）。
- ✅ V25（问候与快捷入口）：2026-08-21 完成。问候语（早晚/午/夜，登录显示用户名）+ 「今天」常用入口（当天打开的快捷方式 chips，无当天记录回退最近使用）。Playwright 端到端：chips 渲染。
- ✅ V26（RSS/ATOM 小组件）：2026-08-21 完成。`app/rss.py` 受控抓取（≤3 源、8s 超时、并发 ≤3、10min 缓存、标准库 XML 解析 RSS/Atom）；`PUT /api/settings` 支持 `rss_feeds`（URL 校验、≤3）；`GET /api/rss`；个人设置页订阅管理 + 面板「订阅」折叠卡片。pytest 98 passed；Playwright 端到端：保存订阅 200 → 面板订阅区显示。顺带根治 SQLite `database is locked`（自动提交 + busy_timeout）。
- ✅ V27（公开状态页）：2026-08-21 完成。`GET /api/health/status` 访客可用，仅返回公开链接状态（遵循 public_mode，私密绝不下发）；访客面板卡片显示状态点。pytest 100 passed；Playwright 端到端：访客看到 28 个公开链接状态点。
- ✅ V28（通知通道）：2026-08-21 完成。站点设置 `notify_url/notify_enabled`（默认空/关）；状态相对上次采样变化时向 ntfy/Webhook POST JSON（5s 超时、失败静默）；首次采样视为变化。pytest 103 passed（本地 fixture：变化通知/同状态不通知/关闭不发/失败忽略）。
- ✅ V29（检测配置中心）：2026-08-21 完成。links 新增 `health_enabled/health_interval/health_timeout/health_threshold`（含 ALTER 迁移与备份导入携带）；引擎按链接配置执行（开关排除、间隔采样、超时、连续失败阈值）；管理页链接表单「健康检查」配置组。pytest 106 passed（开关排除/阈值两轮判定/配置往返）。
- ✅ V30（状态导出 API）：2026-08-21 完成。`GET /api/health/export?format=csv|json`（仅本人启用检测链接，含名称/状态/毫秒/时间）。pytest 110 passed。
- ✅ Phase C（V21–V30）全部完成：2026-08-21，提交范围 `2d36084`（V21）→ `16d254e`（V30）。
- ✅ V31（SSO 解绑/换绑）：2026-08-21 完成。`GET /api/sso/status` + `DELETE /api/sso/identity`（本地密码确认、错密 403、未绑定 400、不删本地账号）；个人设置页解绑确认弹窗（密码输入）。pytest 114 passed。
- ✅ V32（RP 发起登出）：2026-08-21 完成。`GET /auth/sso/logout`：本地会话注销 + IdP `end_session_endpoint` + `id_token_hint`（sessions 新增 `sso_id_token` 列）+ 回跳白名单 `PANEL_SSO_LOGOUT_REDIRECTS`（为空仅站内相对路径）。pytest 117 passed（本地 issuer fixture：仅本地/白名单/IdP 跳转）。
- ✅ V33（回程登出）：2026-08-21 完成。`POST /auth/sso/backchannel`：logout_token 验签（JWKS、iss/aud/exp/events 事件）+ `sub`+`sid` 精确下线；未知 sid 幂等 200；伪造/缺事件 401。pytest 123 passed（本地 JWKS + RSA 签名 fixture）。
- ⬜ V34–V40：待执行。
- 2026-08-21 备注：V24 时钟小组件与 V25 问候（前端部分）已随显示优化在 `codex/frontend-display` 先行落地（分支名非 `codex/50-iterations`，未计入版本序列）；V25 的「今天」常用入口未做，V11–V23 与 V25 剩余项仍待执行。
