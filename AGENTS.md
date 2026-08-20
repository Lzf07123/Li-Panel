# Li&Panel 项目协作手册

> 本文件是后续 AI Agent（Codex 等）的「项目宪法」。新会话必须先完整读完本文件与设计文档再动手。

## 一、项目是什么

个人网页快捷方式面板：本地密码 + Li&Pass OIDC 双登录，公开/私密内容分层，站点品牌信息后台可改，FastAPI + SQLite 低占用后端，React + TS + Vite + Tailwind CSS 4 前端，Docker 容器化部署。

## 二、事实来源（动手前按顺序读）

| 内容 | 位置 |
| --- | --- |
| 设计文档（唯一需求事实） | `docs/superpowers/specs/2026-08-20-lipanel-design.md` |
| 实施计划 | `docs/superpowers/plans/2026-08-20-lipanel-implementation.md` |
| 品牌方案与实现速览 | `design-system/lipanel/BRAND.md`、`MASTER.md` |
| 视觉模板（仅首次设计参考） | `Li-Design/` 子模块 |
| 令牌事实 | `frontend/src/index.css` |
| 品牌默认值 | `frontend/src/lib/brand.ts` |

## 三、硬性规则

1. 所有业务查询强制 `user_id` 隔离；跨用户 id 一律 404。
2. SSO 身份键唯一 `(provider, subject)`；邮箱只展示，每次登录刷新。
3. 授权码一次使用；`state`/`nonce` 逐字符校验；机密客户端也带 PKCE。
4. 私密数据服务端过滤，绝不下发；公开链接默认隐藏原始 URL（`/go/{id}`）。
5. 站点可见信息后台可改：运行时以 `site_settings` 为准，`brand.ts` 仅默认值。
6. 令牌只在 `index.css`，品牌默认文案只在 `brand.ts`；组件禁止硬编码 hex 与文案。
7. 前端技术栈保持 React + TS + Vite + Tailwind CSS 4，不做改写。
8. 加速源全部环境变量化：`IMAGE_REGISTRY` 统一基础镜像前缀；apt/pip/npm 各自独立。
9. 完成 = 验证 + 文档：声称完成前给出测试/构建/容器实测输出。

## 四、验证命令

```bash
cd backend && python -m pytest -q
cd frontend && npx tsc --noEmit && npx vite build
docker compose build && docker compose up -d && curl -fsS http://localhost:8000/api/health
docker stats --no-stream lipanel
```

## 五、提交与分支

- 实现分支：`codex/<topic>`，完成后合并回 `main`（保留 merge 记录）。
- 提交消息：`<type>: <中文简述>`（`docs`/`feat`/`fix`/`test`/`chore`/`style`）。
- 每个任务独立提交，便于评审与回滚。

## 六、多 Agent 协作

- 单一事实来源、一个任务一个 owner、并行任务零文件重叠。
- root agent 只依据验证输出验收，不接受无证据的「完成」。
- 品牌方向分歧或需要用户拍板的决策（定位/主色/Logo）→ 停下询问用户。
