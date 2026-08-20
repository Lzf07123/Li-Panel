# Li&Panel

> 一次收藏，触达所有常用入口。

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Role](https://img.shields.io/badge/role-personal-blue)
![Focus](https://img.shields.io/badge/focus-shortcuts-orange)

[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-06B6D4?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

## 目录

- [关于](#关于)
- [功能](#功能)
- [快速开始](#快速开始)
- [加速源](#加速源)
- [SSO 对接](#sso-对接)
- [仓库结构](#仓库结构)
- [许可](#许可)

## 关于

个人网页快捷方式面板：把常用网页收进分组，访客只看公开内容，登录后管理全部。支持本地账号密码与 Li&Pass OIDC 双登录，首次 SSO 登录可绑定已有账号或新建账号。

| 项目 | 内容 |
| --- | --- |
| 身份 | Li& 系列个人工具 |
| 方向 | 快捷方式导航面板 |
| 方式 | FastAPI + SQLite + React 容器化部署 |
| 目标 | 低占用、私密可控、常用入口一次打开 |

## 功能

- 分组与快捷方式管理，图标、描述、标签、内/外网双地址
- 公开/私密分层：访客只看到公开内容；私密数据服务端过滤
- 公开链接默认隐藏原始地址，访客经 `/go/{id}` 跳转
- 站点名称、slogan、Logo、favicon、页脚、备案后台可改，即时生效
- 本地账号 + Li&Pass SSO（授权码 + PKCE S256），SSO 首次登录绑定/新建二选一
- 明暗主题，Li&Design 海玻璃视觉实例化，尊重 `prefers-reduced-motion`

## 快速开始

```bash
cp .env.example .env
# 编辑 .env，至少修改 PANEL_SECRET_KEY
docker compose up -d --build
```

打开 `http://localhost:8000`（默认端口，可用 `.env` 中的 `PANEL_PORT` 调整），首次访问 `/setup` 创建管理员账号。

## 加速源

构建期镜像与软件源全部环境变量化，见 `.env.example`：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `IMAGE_REGISTRY` | `docker.io/library` | python/node 基础镜像共用加速前缀 |
| `APT_MIRROR` | `deb.debian.org` | apt 源 |
| `PIP_INDEX_URL` | `https://pypi.org/simple` | pip/uv 包索引 |
| `NPM_REGISTRY` | `https://registry.npmjs.org` | npm 源 |

## SSO 对接

1. 在 Li&Pass 门户创建客户端，回调地址填 `https://你的域名/auth/sso/callback`
2. `.env` 中填写 `OIDC_ENABLED=true`、`OIDC_ISSUER`、`OIDC_CLIENT_ID`、`OIDC_CLIENT_SECRET`（机密客户端）、`OIDC_REDIRECT_URI`
3. 重启容器，登录页出现「Li&Pass SSO 登录」

## 端口与反代

- `docker compose up -d` 后，对外只暴露一个端口 `PANEL_PORT`（默认 `8000`），由内置 **nginx** 反代到后端 `lipanel:8000`；后端真实端口不直接映射到宿主机（`docker ps` 中仅 `lipanel-nginx` 发布端口）。
- nginx 配置见 `nginx/nginx.conf`（代理头 `X-Real-IP`/`X-Forwarded-*`、上传上限 10m、gzip）。
- 反向代理 HTTPS 时，在外部反代/Nginx 设置 `PANEL_COOKIE_SECURE=true`、`PANEL_HSTS=true`，并透传 `X-Forwarded-Proto`（后端 uvicorn 默认信任代理头）。
- 开发直连后端可本地运行 `PANEL_PORT=8000 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`。

## 仓库结构

```text
Li&Panel/
├── backend/          # FastAPI + SQLite
├── frontend/         # React + TS + Vite + Tailwind CSS 4
├── design-system/lipanel/  # Li&Design 实例化方案
├── Li-Design/        # 视觉模板子模块（仅首次设计参考）
├── docs/superpowers/ # 设计文档与实施计划
├── compose.yaml
├── Dockerfile
└── .env.example
```

## 部署加固（V47）

- **镜像版本钉扎**：生产构建请将 `compose.yaml` 中 `image: lipanel:local` 改为固定版本（如 `lipanel:0.1.0`），避免意外覆盖；`.env.example` 已给出全部可配变量。
- **反向代理 HTTPS**：容器默认 HTTP（`PANEL_COOKIE_SECURE=false`）。经 Nginx/Caddy 终止 TLS 时设置 `PANEL_COOKIE_SECURE=true`，并配置 `X-Forwarded-Proto`/`X-Forwarded-Host` 透传；HTTPS 部署建议开启 `PANEL_HSTS=true`。
- **Host 白名单**：设置 `PANEL_ALLOWED_HOSTS=panel.example.com,*.example.com` 防 DNS rebinding；为空则放行。
- **数据持久化**：全部业务数据落在 `./data`（compose bind mount，`docker compose down` 不会删除，重建镜像/容器均不受影响，只有加 `-v` 才会清空）。SQLite 为 WAL 模式，运行中会生成 `panel.db-wal`/`panel.db-shm`，直接拷贝备份时请三者一并复制，或先 `docker compose stop` 再复制。Linux 部署请确保 `./data` 属主为容器用户 uid 10001（如 `sudo chown -R 10001:10001 ./data`），否则容器内无写权限。
- **备份恢复演练**：数据在 `./data`（挂载卷）。定期在管理页「个人设置 → 数据备份」导出 JSON 并异地保存；演练流程：导出 → 清空数据目录 → 重新初始化 → 导入备份 → 核对分组/链接数量与公开可见性。
- **`PANEL_SECRET_KEY` 轮换**：生产要求 ≥32 字符随机串；轮换会使现有会话失效（需重新登录），建议在低峰期操作，并先备份数据。

## 许可

© 2026 Li&Panel。保留所有权利。
