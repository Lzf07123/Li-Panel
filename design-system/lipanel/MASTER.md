# Li&Panel 实现速览（MASTER.md）

日期：2026-08-20

## 令牌（事实来源：`frontend/src/index.css`，前缀 `lipanel`）

- 浅色：bg `#f6fbf9`、surface `#ffffff`、surface-2 `#eef6f3`、fg `#35423f`、muted `#71807a`、border `#e1ece8`、primary `#25786d`、ring `#25786d`
- 深色：bg `#3a3f45`、surface `#434950`、surface-2 `#4b5259`、fg `#f0f2f4`、muted `#b8c0c7`、border `#545c64`、primary `#7fd4c6`、ring `#7fd4c6`
- 按钮：半透明单色（浅 10%/深 13%）+ 细描边 + `::after` 扫光
- 阴影：`--shadow-sm/md/lg` 水绿 tint，透明度总和 < 0.1
- 动效：`--motion-fast/base/slow = 150/250/350ms`；只动 transform/opacity/background-position
- 科技光效：网格 12s、光束 10s（错峰 0.8/4.2/7.5s）、光点 6s；`prefers-reduced-motion` 单帧

## 组件清单

- 基础：`.btn`（primary/secondary/ghost/danger/link + 主按钮扫光）、`.card`（+ `.card-signature` 渐变描边、`.card-halo` 呼吸辉光）、`.input`、`.label`、`.badge-*`、`.notice-*`、`.modal-*`、`.toast-*`、`.table-shell`、`.tabs-scroll`
- 反馈：`.page-enter`、`.shimmer`、`.spinner`、`PageSkeleton`、`BlurText`、`CountUp`
- 弹窗/提示：`Modal` / `ConfirmDialog`（z-70）、`ToastProvider` + `useToast`（z-80，带进度条）
- 氛围：`AuroraBackground`（soft 档）、`FloatingBackground`（Canvas，无依赖，reduced-motion 单帧）、`TechAmbience`（纯 CSS 网格/光束/光点）
- 主题：`ThemeToggle` + `lib/theme.ts` 读写 `lipanel-theme`，切换 `html.dark`

## 响应式

- 断点：375 / 768 / 1024 / 1440；面板网格 1→2→3→4 列
- 顶栏移动端只显示图标；管理标签横滑（`tabs-scroll`）；表格 `overflow-x-auto` 横向滚动
- 移动端氛围减量：光点/光束隐藏、网格停用、极光仅 1 枚光斑
- `prefers-reduced-motion`：所有循环动效收敛为单帧或静态渲染

## 页面模式

| 页面 | 外壳 | 氛围浓度 |
| --- | --- | --- |
| `/setup`、`/login`、`/sso/link` | AuthShell（`max-w-md` 居中卡 + 品牌 + 备案） | 默认（10 + TechAmbience） |
| `/` 面板 | AppHeader + `max-w-7xl` 内容 | 10（soft） |
| `/settings` 管理 | AppHeader + 表单/卡片 | 4×0.5 |

## 验收状态

2026-08-20 首版交付实测（含全量设计升级）：

- 后端：pytest 35 passed（认证/SSO/可见性/隔离/站点设置）
- 前端：`tsc --noEmit` + `vite build` 通过；产物 JS gzip 82.0KB、CSS gzip 7.7KB（全量组件库）
- 容器：`docker stats` 实测内存 46.09MiB、CPU 0.21%、2 个进程（目标 50–90MB，达标）
- 端到端：初始化管理员 → 登录 → 建分组/链接 → 访客面板（私密不可见、URL 隐藏）→ `/go/{id}` 302 跳转 全部通过
- 加速源：`IMAGE_REGISTRY=docker.m.daocloud.io/library` 完成镜像构建验证

视觉对照 Li&Design 第 6 章清单的自动化部分已核对；四档响应式与对比度建议在浏览器中人工复核。
