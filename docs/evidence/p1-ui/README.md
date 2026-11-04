# P1 UI 证据（2026-11-04）

本目录用于 P1（W4–W7）前后对比。所有截图都是**真实构建的 Vue 应用**在本地 mock API 下的运行截图；mock 数据只用于让管理端/用户端有可渲染的记录，不是生产数据截图。

## 环境

| 项 | 值 |
|---|---|
| 基线（Before） | commit `4390152`（P0 分支 head，即本 PR 的父提交） |
| 变更（After） | 本 ticket 分支 `agent/implement-p1-a419ed295720` |
| 视口 | 1440 × 1000，桌面 Chrome（Playwright Chromium） |
| 前端开关 | `VITE_USE_MOCK=false`、Agent/Admin 均走真实 `/api/*` 路径 |
| API | 本地 mock server，脚本与 fixtures 不在仓库内；地图 fixture 的小区坐标、租金、评分从开发库只读聚合（60 个小区 / 426 套），会话/图片/口碑 fixture 为构造数据 |
| 天地图 | agent 环境没有 `TIANDITU_API_KEY`，**瓦片请求未实际发生**；地图截图显示的是无 Key 时的坐标降级视图（真实坐标 + 网格 + 明确提示），不代表线上有底图的效果 |

## 对比

| 场景 | Before | After |
|---|---|---|
| 用户端地图 tab | `before-chat-map.png`：仍为“即将”占位，无真实坐标 | `after-chat-map.png`：真实小区 marker、小区/房源数、租金/评分着色、通勤筛选、点击弹出代表房源 |
| 房源详情证据 | `before-detail-evidence.png`：只有评分/通勤/价格等 P0 内容，无图片/口碑 | `after-detail-evidence.png`：封面分析（重复图/低价信号、视觉未授权提示）+ 口碑证据（来源、链接、置信度、待确认不计分） |
| Agent 评测 | `before-admin-agent-eval.png`：写死设计值 | `after-admin-agent-eval.png`：60 条规则基线真实结果、历史回归、失败样例 |
| Agent 成本/护栏 | `before-admin-agent-cost.png`：写死演示值 | `after-admin-agent-cost.png`：真实会话 token/兜底/工具/护栏/模型额度聚合 |
| 图片 / AI | `before-admin-images.png`：明确占位，按钮 disabled | `after-admin-images.png`：真实候选队列、封面缩略图、dHash 重复组、假房源信号与证据 |
| 口碑证据 | `before-admin-quality.png`：数据质量页，导航无“口碑证据” | `after-admin-reputation.png`：新增口碑证据页（高风险/待补小区、录入/抽取、确认/排除） |

## 说明

- Before 截图里的“评测/成本/图片”页面在 P0 中是静态设计预览，因此与 After 的同一 tab/页面直接对照。
- 地图截图没有天地图底图是环境限制，不是实现限制；后端瓦片代理、缓存与前端瓦片层已实现，配置 Key 后会加载 `vec`/`cva` 两层。
- 截图不含 `.env`、Token、私人地址或飞书内容；地图中的小区/租金来自公开房源聚合，仅用于自用开发验证。
