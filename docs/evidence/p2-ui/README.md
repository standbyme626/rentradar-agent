# P2/P3 UI 证据（2026-11-04）

本目录是 P2/P3 的**前后对比截图**。Before = P1 分支 head `2fc904a`（本 ticket 的基线）；After = 本 ticket 分支。截图均为真实构建的 Vue 应用，在本地 mock API 下打开；mock 只提供渲染所需记录，不是生产数据。

| 项 | 值 |
|---|---|
| Before | commit `2fc904a`（P1 head，包含 P0） |
| After | `agent/implement-p2-p4-5fe8bf7e4a90` |
| 视口 | 1440 × 1000，桌面 Chrome（Playwright Chromium），full page |
| 前端开关 | `VITE_USE_MOCK=false`（真实 `/api/*` 路径） |
| API | 本地 mock server（脚本/fixtures 未入库），真实接口形状 |
| 生产数据 | **未使用**；agent 无生产库/凭据 |

## 对比

| 场景 | Before | After |
|---|---|---|
| 采集任务页 | `before-admin-tasks.png`：只展示任务 1/2 与分片覆盖，没有任务管理、来源/城市维度 | `after-admin-tasks.png`：新增“全部任务”表（城市/来源/节奏/启停/编辑/运行）与“新建任务”入口；侧栏新增“运维” |
| 设置页 | `before-admin-settings.png`：只有预算/通知/账号/审计 | `after-admin-settings.png`：新增“运维告警”阈值卡（队列/超时/磁盘/备份/冷却/间隔）与“运维告警推送”开关 |
| 运维页 | 无此页面 | `after-admin-ops.png`：状态卡、告警列表、只读分享 token、来源/城市开关、参考租金导入 |
| 只读访问 | `before-public-readonly.png`：未登录只能到登录页，没有公开只读视图 | `after-public-readonly.png`：`/share/<token>` 聚合看板（总量/区域/价格带/覆盖），无标题/图片/地址/联系方式 |
| 图片/AI | `before-admin-images.png`：视觉标签“未授权 · 不调用”，队列无视觉标签 | `after-admin-images.png`：启用 OpenCode Go 视觉标签后，队列显示标签与置信度，页头/管线说明同步 |

## 说明

- 公开页截图用的 token 是本地 mock 的演示 token，不对应任何真实分享链接。
- 运维页的备份目录 `/home/kkk/backups/rentradar`、磁盘、告警为 mock 展示；真实备份/恢复未在本环境执行（无 Docker/psql）。
- Before 的任务/设置截图与 After 使用同一 mock API fixture，确保差异只来自前端改动。
- 图片页 After 截图把 mock 的 `vision_enabled` 设为 true 并附带视觉标签 fixture，用于展示启用后的 UI；Before 为 P1 的未启用状态。真实视觉调用证据见 PR 描述（单张封面返回“图文不符”95%）。
- 截图不含 `.env`、Token、私人地址或飞书内容。
