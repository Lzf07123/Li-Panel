# Li&Panel 更新日志

## 0.1.0（2026-08-21）

### 存活检测分批探测与分批显示（2026-08-22）

- **分批检测**：客户端探测改为每批 `CLIENT_PROBE_BATCH_SIZE`（6 个）并发发起、批间串行——目标多时不再一次性铺满全部请求，避免打爆目标站点/浏览器连接池，也便于逐批反馈进度。
- **分批显示**：每批完成后统一回调一次（整批刷新状态点 + 更新「检测中 {done}/{total} 批」进度指示，全部完成后自动消失）；批内仍保留逐条流式点亮，首个快链接约 100ms 出现，兼顾即时反馈与批量进度。
- 手动「重新检测」、刷新同步探测、120s 常驻探测均走同一批处理流程。
- 验证：前端 vitest 40 passed（+3：批间串行/并发上限、onBatch 进度回调、批内流式顺序）；tsc / vite build / oxlint 通过；后端 pytest 212 passed（无后端改动，回归）。

### 手动触发存活检测（2026-08-22）

- **顶栏新增「重新检测」按钮**：面板页右上角（管理/退出 左侧，访客视图同样可用）手动触发存活探测——登录用户同时发起浏览器直连探测（绕过 30s 节流）与服务端强制刷新（绕过前端 60s 节流，后端 30s 兜底），访客仅走服务端公开状态刷新；探测期间按钮显示进度并禁用，完成后 Toast 反馈（无启用健康检查的链接时给出提示）。
- **修复客户端探测从未真正执行**：`/api/panel` 的登录用户链接此前未下发 `health_enabled` 等字段（前端类型要求但序列化遗漏），导致浏览器直连探测目标恒为空、状态点只依赖服务端；本次补发 `health_enabled/health_interval/health_timeout/health_threshold`，访客公开视图仍不下发（隐私不变）。
- **探测目标收集收敛到 `probe.ts`**：`collectProbeTargets` 统一「启用健康检查 + http(s) 地址」规则，面板探测与本地缓存清理共用。
- 验证：pytest 212 passed（+1：面板健康字段仅登录可见）；前端 vitest 37 passed（+3：目标收集/URL 回退/协议过滤）；tsc / vite build / oxlint 通过。

### 图标抓取逻辑加强（2026-08-22）

- **魔数识别（`_sniff_ext`）**：不依赖 Content-Type，按文件头识别 PNG/JPEG/GIF/WEBP/ICO/文本 SVG。修复两类真实失败：
  - Docker Hub：`favicon.ico` 以 `application/octet-stream` 返回（实际为 PNG），此前被拒；
  - Cloudflare：`favicon.ico` 声明 `image/x-icon` 但内容实为 PNG，此前会存错扩展名。
- **页面大小上限独立**：首页 HTML 解析候选上限放宽到 5MB（`MAX_PAGE_BYTES`，图标本体仍限 1MB）。修复 Cloudflare 首页 1.3MB 超限导致候选从未解析的问题。
- **父域兜底**：自身域名全部候选失败（如 dash.cloudflare.com 的 403 JS 挑战）时，尝试父域名根 `/favicon.ico`（dash.cloudflare.com → cloudflare.com/favicon.ico）。
- **候选去重**：同一候选 URL 只请求一次（link 候选与根回退重复场景）。
- 支持 GIF favicon（Content-Type 白名单补充 `image/gif`）。
- 验证：pytest 202 passed（+8）；真实站点实测 6/6 成功（hub.docker.com / www.docker.com / cloudflare.com / www.cloudflare.com / dash.cloudflare.com / developers.cloudflare.com，修复前仅 1/6）。

### 图标抓取后台化与超时预算（2026-08-22，修复登出/添加快捷方式卡顿）

- **自动抓取改独立 daemon 线程**：创建/编辑链接后的 favicon 抓取不再挂在 FastAPI `BackgroundTasks`/请求生命周期上（此前会占用 keep-alive 连接，批量添加时后续登出、继续添加请求可能排队卡顿）。
- **并发槽**：自动抓取线程全局限 4 个同时活跃，其余排队，防止批量导入时线程与出站请求堆积。
- **总超时预算**：`fetch_favicon` 支持 `total_budget`（默认 25s），候选递归与父域兜底共享 deadline，慢站点不再无限叠加超时。
- 验证：pytest 205 passed（+3：响应不阻塞/过期 deadline 不再发请求/预算传递）；端到端实测连续创建 8 个慢抓取链接 0.04s、登出 0.00s、再添加 0.00s。

### CSRF 校验兼容反代端口剥离（2026-08-22，修复公网 IP:端口访问下登出/添加 403）

- **根因**：上一轮 CSRF 加强为「完整 host+port 比较」，但 nginx `proxy_set_header Host $host` 会**剥离端口**（`$host` 不含端口）；公网以 `http://IP:8000` 访问时，浏览器 Origin 带 `:8000` 而后端收到无端口 Host → netloc 不匹配 → 所有写请求（登出/添加链接等）403。
- **修复**：`X-Forwarded-Host` 存在时按完整 netloc 严格校验（堵同 host 不同端口）；未透传时回退 hostname 比较（兼容现有 nginx 配置，SameSite=Lax 兜底）。
- **nginx**：`proxy_set_header X-Forwarded-Host $http_host;` 透传原始 Host（含端口），让新部署启用严格模式。
- 验证：pytest 207 passed（+2）；端到端实测 Host 无端口 + Origin 带端口 → 建组/建链/登出全部放行，X-Forwarded-Host 不同端口仍 403。
- 部署提示：仅更新后端容器即可恢复（回退 hostname 比较）；重建 nginx 容器后启用严格模式。

### 健康检查（存活测试）节流修复（2026-08-22）

- **根因**：前端在窗口聚焦/标签页恢复可见时每次都 `refresh=true` 强制健康检测（忽略服务端 60s 缓存），频繁切换窗口会反复触发后端同步出站检测全部链接——链接多/目标站点慢时请求堆积、状态点转圈或失败，表现为「概率无法使用」。
- **前端**：强制检测节流 60s（与服务端缓存 TTL 一致），窗口内重复触发降级为普通请求直接命中缓存。
- **后端**：`/api/health/links` 与 `/api/health/status` 的 `refresh=1` 增加每用户/IP 30s 节流，多标签页/多设备也无法绕过前端反复强制出站。
- 验证：pytest 209 passed（+2：节流窗口单测、refresh 二次请求不再出站）；Playwright 实测 8 次焦点/可见性切换全部命中缓存、0 次强制出站。

### 客户端存活探测（2026-08-22）

- **探测从浏览器发起**：登录用户的面板状态点改为由浏览器直连目标 URL（`HEAD` + `no-cors` + 5s 超时 + 并发 6）探测；自动使用系统/浏览器代理（含扩展代理），解决服务端网络与客户端网络不一致（如客户端需代理才能访问的站点）。
- **刷新同步探测**：刷新/首次进入页面时，panel 与登录态就绪后立即发起客户端探测；窗口聚焦/恢复可见在 30s 节流内也触发。
- **服务端保留为兜底**：客户端结果优先展示；服务端探测继续维护历史/趋势/通知，并补齐访客视图与未暴露 URL 的链接（隐私安全：访客不探测私密链接）。
- **CSP**：`connect-src` 放宽为 `'self' https: http:`（允许浏览器直连探测目标；无 XSS 面，风险可控）。
- 验证：pytest 209 passed；前端 vitest 21 passed（+4：probe 工具可达/失败/超时/并发）；Playwright 实测首次进入与刷新均发起外部 HEAD（可达→up、不可达→down）、无 CSP 违规。

### 客户端探测提速（2026-08-22）

- **全并发探测**：移除 6 个一批的串行分批，全部目标同时发起（浏览器连接池自然排队），总耗时 ≈ 最慢单个（≤5s），不再「批次数 × 最慢批次」。
- **流式更新**：`probeFromClient` 新增 `onResult` 逐条回调，每个目标完成立即点亮状态点——首个快链接约 100ms 出现，不必等全部探测完成。
- **本地缓存占位**：探测结果写入 localStorage（10 分钟有效），刷新/重开页面立即渲染上次状态（约 800ms 内出现），后台探测完成后覆盖更新。
- 验证：前端 vitest 23 passed（+2：流式回调顺序、缓存读写/过期/损坏容错）；Playwright 实测首个状态点 1014ms、刷新后 832ms（此前需等全部探测，最坏 5s+）。






### 后台快捷方式筛选增强（2026-08-22）

- **管理页筛选栏**：快捷方式表格上方新增筛选栏，支持四维条件同时生效：
  - 关键词：名称 / 描述 / 标签 / 生效地址 / 内网地址 / 外网地址（忽略大小写）；
  - 分组：全部分组 / 指定分组 / 未分组；
  - 可见性：全部 / 公开 / 私密；
  - 健康检测：全部 / 启用检测 / 关闭检测；
  - 标签：多选 chips，任一命中（OR）语义。
- **交互细节**：全选只作用于筛选结果；表头显示「命中数/总数」；无匹配时显示空态提示；「清除筛选」一键重置全部条件。
- **逻辑抽离**：筛选条件实现为 `frontend/src/lib/filters.ts` 纯函数（`matches` + `passesManageFilters`），面板页搜索同步复用共享 `matches`（并补齐内/外网地址搜索，原实现只搜生效地址）。
- 验证：前端 vitest 34 passed（+8：filters 关键词/多标签 OR/分组/可见性/健康开关/组合）；tsc / vite build / oxlint 通过。

### 存活探测增强与探测流程优化（2026-08-22）

- **服务端探测引擎复用**：`app/health.py` 改用共享 `httpx.Client`（keep-alive 连接复用），`routers/health.py` 改用模块级线程池（全局并发仍 ≤4），去掉每请求新建线程池、每链接新建客户端的开销。
- **同链接探测合并（single-flight）**：同一链接的在途探测全局去重，多标签页/并行请求共享一次出站结果，不再重复打爆目标站点；修复了合并实现中「任务完成过快时回调自锁」的潜在死锁（fast-path 回归测试覆盖）。
- **通知异步化**：状态变化通知改由后台 daemon 线程发送，批量故障（如整片站点离线）时 webhook 不再串行阻塞面板响应（原单条最多 5s，20 条可能卡 100s）。
- **容器存活检查增强**：`/api/health` 增加 SQLite `SELECT 1` 就绪检查，数据库损坏/数据目录不可用时返回 503，Docker healthcheck 立即把容器标记为 unhealthy（curl `-f` 对 503 返回失败）。
- **前端探测尊重 `health_enabled`**：客户端探测只对已启用健康检查的链接发起（修复后台关闭检测后状态点仍被浏览器探测点亮的不一致）；面板加载时清理本地缓存中已删除/停用链接的残留结果（`pruneProbeCache`）。
- **面板常驻周期探测**：面板打开期间客户端每 120s 自动直连刷新（受 30s 节流约束）、服务端每 5min 走缓存兜底刷新，状态不再依赖切窗口才更新。
- 验证：pytest 211 passed（+2：single-flight 合并、`/api/health` DB 故障 503；异步通知用例改为等待送达）；前端 vitest 26 passed（+3：prune 清理/过期/空集合）；tsc/vite build/oxlint 通过。

### 超长 URL 显示修复（2026-08-22）

- **后台快捷方式表格**：URL 列在所有断点统一单行截断 + 省略号（原桌面端恢复自然换行，298 字符 URL 会把行撑高至 164px 且无省略号）；单元格增加 `title` 悬停查看全文；列宽统一由 `.table-cell-clip`（11rem）控制。
- **命令面板**：列表项 label 优先完整显示（`flex-1 min-w-0`），hint 压缩至最多 45% 宽度并截断；hint 增加 `title` 悬停查看全文（原长描述/URL 会把名称挤压到只剩数像素）。
- **内置窗口预览**：URL 行补充 `title` 悬停提示。
- 验证：Playwright 实测超长 URL（298 字符）——表格单元格高度 164px→52px 且显示省略号、命令面板名称 23px→264px 完整、hint 截断；tsc/vite build/vitest 17 passed。


### 上线前全面审查修复（第二轮，2026-08-21）

- **安全（P1）**：`PANEL_HOST_COOKIE=true` 时会话管理接口（列表/吊销单个/全量吊销）改从 `settings.session_cookie` 读取 Cookie，修复 `__Host-` 模式下 current 标记恒为 false、可误吊销当前会话的问题；新增 3 条回归测试。
- **安全（P2）**：启动校验 `PANEL_HOST_COOKIE=true` 必须同时 `PANEL_COOKIE_SECURE=true`（`__Host-` 前缀要求 Secure）；新增测试。
- **安全（P2）**：`GET /uploads/{name}` 文件名增加单段安全字符白名单（与 `/favicons` 一致），纵深防御编码斜杠路径穿越；新增 2 条测试。
- **安全（P3）**：CSRF Origin 校验改为比较完整 host+port（默认端口 80/443 归一化），堵住同 host 不同端口缺口；新增 3 条测试。
- **安全（P3）**：SSO 发起入口（`/auth/sso/login`）与回调一致按 IP 限流；`sso_flows` 增加滚动清理（过期立删、已消费超 1 天删除）；新增 2 条测试。
- **缓存（P3）**：SPA 入口 index.html 增加 `Cache-Control: no-cache`，发版后即时生效；新增测试。
- **Host 白名单（P3）**：改用 `urlparse` 解析 Host 头，兼容 IPv6 字面量 `[::1]:port`；新增 2 条测试。
- **i18n（P3）**：设置页 slogan 字段中文界面显示「标语」（原为英文 `slogan`），en-US 映射 "Slogan"。
- **前端（P3）**：ToastProvider 标题随语言切换即时更新（补 `DEFAULT_TITLES` 依赖）；PanelPage/SettingsPage 消除 exhaustive-deps 警告。
- 验证：pytest 194 passed（+14）、tsc/vite build/vitest 17 passed、oxlint 仅剩 3 条 fast-refresh 风格警告。


### 上线前审查修复（2026-08-21）

- **安全**：修复 SPA 回退路径穿越（编码 `..` 可下载 `data/panel.db` 等任意文件）；通知 webhook（`notify_url`/`notify_enabled`）仅管理员可见；登录锁定到期后自动解除；SSO 回调/RP 登出全链路使用配置的会话 Cookie 名（`PANEL_HOST_COOKIE` 生效）；登出回跳拒绝反斜杠防开放跳转。
- **部署**：compose 补齐全部运行期环境变量透传（Host 白名单/HSTS/登录锁定/图标抓取/健康检查/备份保留/SSO 回跳等此前在容器内失效）；后端固定监听容器内 8000，`PANEL_PORT` 仅作宿主机对外端口，改端口不再导致反代断链；`NPM_REGISTRY` 经 `npm ci --registry` 真正生效（此前被 `frontend/.npmrc` 覆盖）；VITE_* 品牌构建参数接入 Docker 构建；nginx `gzip_types` 补 `text/javascript` 并开启 `gzip_static`/`gzip_vary`。
- **脚本**：冒烟脚本导入断言改用链接总数（同名分组合并后 `groups+ungrouped` 不再增长）。
- **启动容错**：数据目录不可写时启动报错改为可操作提示；compose 新增 `data-init` 一次性服务自动修正 `./data` 属主为 uid 10001；`scripts/fix-data-owner.sh` 保留作手动修复，README 补充 SELinux `:Z` 说明。
- **页脚重复版权**：`footer_text` 默认改为空（前端固定渲染 `© 年 品牌 · v版本`），启动时自动清理旧库遗留的 `© 2026` 重复值。
- **备案信息优先级**：备案字段（ICP/公安）优先读取构建期环境变量 `VITE_ICP_*`/`VITE_POLICE_*`；后台修改对应字段时页面给出提醒（不生效，需清除变量后重新构建）。
- **版权行可配置**：站点设置新增 `copyright`，页脚「© 年份 名称 · v版本」可在后台修改；留空时自动生成（持有人跟随站点名称）。
- **按钮语义增强**：`AsyncButton` 默认显式 `type=button`；链接卡片状态点键盘可达（Enter/空格，`aria-haspopup`）；SSO 绑定/新建与可见性切换按钮补 `aria-pressed`；命令面板输入框与选项列表 `aria-controls`/`aria-activedescendant` 联动。
- 验证：pytest 177 passed（新增 6 项回归）；tsc/vite build/vitest 13 passed；镜像重建后健康检查、`docker stats` 46.66MiB、gzip 压缩、冒烟 PASS。

### 50 版本迭代（V01–V50 全量完成）

- **Phase A 搜索与导航（V01–V10）**：`/` 聚焦搜索、键盘导航、外部搜索回退、标签筛选、最近使用、`Ctrl/⌘+K` 命令面板、内置窗口、分组折叠记忆、空状态引导、可达性。
- **Phase B 排序与数据（V11–V20）**：链接/分组拖拽排序、分组图标与配色、链接图标自动抓取、批量操作、标签管理、重复检测、JSON 备份导出/导入、自动快照、恢复向导。
- **Phase C 状态与感知（V21–V30）**：链接健康检查引擎（受控出站）、卡片状态点、状态历史趋势、时钟与问候、「今天」常用入口、RSS/ATOM 小组件、公开状态页、通知通道、检测配置中心、状态导出 API。
- **Phase D 安全（V31–V40）**：SSO 解绑、RP 发起登出、回程登出、Host 白名单、登录锁定、角色权限、会话管理、审计日志、安全响应头、密钥与上传加固。
- **Phase E 交付治理（V41–V50）**：PWA 清单、离线缓存外壳、i18n 框架与语言偏好、静态资源长期缓存、版本信息、部署加固文档、前端测试、端到端冒烟脚本、性能回归。

### 既有功能

- 本地密码 + Li&Pass OIDC 双登录（PKCE、state/nonce/at_hash 全量校验）
- 公开/私密内容分层、访客视图与 `/go/{id}` URL 隐藏
- 站点品牌信息后台可改（`site_settings` 运行时事实来源）
- Docker 容器化部署（约 46MiB 内存目标，实测达标）
