# Li&Panel 更新日志

## 0.1.0（2026-08-21）

### 上线前审查修复（2026-08-21）

- **安全**：修复 SPA 回退路径穿越（编码 `..` 可下载 `data/panel.db` 等任意文件）；通知 webhook（`notify_url`/`notify_enabled`）仅管理员可见；登录锁定到期后自动解除；SSO 回调/RP 登出全链路使用配置的会话 Cookie 名（`PANEL_HOST_COOKIE` 生效）；登出回跳拒绝反斜杠防开放跳转。
- **部署**：compose 补齐全部运行期环境变量透传（Host 白名单/HSTS/登录锁定/图标抓取/健康检查/备份保留/SSO 回跳等此前在容器内失效）；后端固定监听容器内 8000，`PANEL_PORT` 仅作宿主机对外端口，改端口不再导致反代断链；`NPM_REGISTRY` 经 `npm ci --registry` 真正生效（此前被 `frontend/.npmrc` 覆盖）；VITE_* 品牌构建参数接入 Docker 构建；nginx `gzip_types` 补 `text/javascript` 并开启 `gzip_static`/`gzip_vary`。
- **脚本**：冒烟脚本导入断言改用链接总数（同名分组合并后 `groups+ungrouped` 不再增长）。
- **启动容错**：数据目录不可写时启动报错改为可操作提示；compose 新增 `data-init` 一次性服务自动修正 `./data` 属主为 uid 10001；`scripts/fix-data-owner.sh` 保留作手动修复，README 补充 SELinux `:Z` 说明。
- **页脚重复版权**：`footer_text` 默认改为空（前端固定渲染 `© 年 品牌 · v版本`），启动时自动清理旧库遗留的 `© 2026` 重复值。
- **备案信息优先级**：备案字段（ICP/公安）优先读取构建期环境变量 `VITE_ICP_*`/`VITE_POLICE_*`；后台修改对应字段时页面给出提醒（不生效，需清除变量后重新构建）。
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
