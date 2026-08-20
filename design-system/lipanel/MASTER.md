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

- 基础：`.btn`（primary/secondary/ghost/danger/link）、`.card`、`.input`、`.label`、`.badge-*`、`.modal-*`、`.toast-*`、`.table-shell`（按需）
- 反馈：`.page-enter`、`.shimmer`、`.spinner`
- 氛围：`TechAmbience`（纯 CSS 网格/光束/光点，`aria-hidden` + `pointer-events: none`）
- 主题：`lib/theme.ts` 读写 `lipanel-theme`，切换 `html.dark`

## 页面模式

| 页面 | 外壳 | 氛围浓度 |
| --- | --- | --- |
| `/setup`、`/login`、`/sso/link` | AuthShell（`max-w-md` 居中卡 + 品牌 + 备案） | 默认（10 + TechAmbience） |
| `/` 面板 | AppHeader + `max-w-7xl` 内容 | 10（soft） |
| `/settings` 管理 | AppHeader + 表单/卡片 | 4×0.5 |

## 验收状态

随实现任务更新；最终对照 Li&Design 第 6 章清单在 Task 20 回填。
