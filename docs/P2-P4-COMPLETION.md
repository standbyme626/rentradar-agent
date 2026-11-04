# P2–P4 完成度与验收记录（2026-11-04）

> 计划书：`docs/PLAN-2026-11-03.md`（PR #2）。本分支基于 P0（PR #3）→ P1（PR #4）继续，PR 堆叠关系见根 README。
> 结论：**代码侧 W8/W9 与剩余收口项已完成；计划书第 6 节中依赖生产数据/人工/外部 Key 的验收项仍需 operator 执行**，不计入“已由代码验证”。

## 1. 阶段映射

计划书本身只标了 P0/P1/P2 三个优先级。为了让 P2/P3/P4 可验收，本分支按“剩余工作流”映射：

| 阶段 | 内容 | 对应计划书 |
|---|---|---|
| P2 | 运维/CI/公网只读 + 多城市/多来源 | W8、W9 |
| P3 | 参考租金/开放数据、原生 tool_calls、AI Provider 切换、视觉标签、真实第二房源源 | W4/W5 收口、Track B 第 13 项、W9 |
| P4 | 文档/README、验收记录、证据、剩余人工项 | 第 6 节、第 8 节 |

## 2. 本轮交付（代码可验证）

| 项 | 交付 | 验证 |
|---|---|---|
| 模型接入 | 新增 `opencode_go_deepseek` Provider（OpenCode Go · DeepSeek V4.1 Flash），优先级 5，高于 ModelScope 兜底；AI 日上限统一走 `aiDailyCap` | 单测 + 真实调用：`deepseek-v4.1-flash`，约 2.8s，`prompt_tokens=33/completion_tokens=12`；原生 tool_calls 真实返回 `search_listings` 调用 |
| CI | `.github/workflows/ci.yml`：后端 ruff+pytest、Postgres 迁移升降级、前端构建 | YAML 解析通过；本地等价命令全绿 |
| 告警 | `alert_service.py` + scheduler `alert_check` + worker + 管理端「运维」页；队列/源失败/Provider/磁盘/备份阈值与冷却 | 告警阈值/恢复/格式单测；`ops/status` 路由注册 |
| 备份恢复 | `backup.sh` 写 `last_backup.json`、失败 marker；新增 `restore-drill.sh` 临时库演练 | `bash -n` 通过；受环境限制未实际跑 Docker/psql |
| 只读分享 | `share_links` 表、SHA-256 存 token、创建/撤销、60 次/分限流、`X-Robots-Tag: noindex`、`/share/:token` 聚合页 | 单测 + 路由注册；页面不含标题/图片/地址/联系方式 |
| 多城市 | 已有 `cities` 表接管理 API/UI；每城市独立启用/停用、任务与库存统计；scheduler 单任务异常不再中断整轮 | 路由注册；任务/City 单测未覆盖 DB 路径，如实标注 |
| 多来源 | 来源管理 API/UI；`manual` JSON/CSV 导入源；`ziroom` 公开列表 API（默认停用，PNG 精灵图价格解码）已接入；跨源同房源按小区/户型/租金/面积去重并记录 alias | 解析/精灵图/去重单测；真实抓取需 operator 启用 |
| 参考租金 | `reference_rents` 表、导入/删除 API、CLI；评分价格项有参考价时优先于挂牌中位价 | normalize/pick 单测；SQL 迁移离线生成通过 |
| 视觉标签 | `APP_IMAGE_VISION_ENABLED=true` 时调用 OpenCode Go 视觉模型，标签+置信度写入 `quality.vision` 并映射为可解释信号；失败保留“待视觉” | 真实封面调用通过（返回“图文不符”95%）；单测覆盖解析/信号映射 |
| 原生 tool_calls | Provider 支持 tools；`plan_tools_native` + `APP_AGENT_NATIVE_TOOLS` 开关；失败自动回退严格 JSON/rules | 真实 spike 通过；开关默认 false，避免未经生产验证就改变主链路 |
| 文档 | `README.md`、`docs/OPS.md`、本文件；MEMORY/HANDOFF/API-SOURCES 更新 | — |
| 本地验证 | 后端 `pytest -q` 154 passed、`ruff check` 全绿；前端 `vue-tsc` + `npm run build`（`VITE_USE_MOCK=false`）通过；迁移离线 SQL 生成通过 | 见本文件“完成度口径” |

## 3. 计划书第 6 节逐项状态

| 验收项 | 代码 | 生产/人工 |
|---|---|---|
| 5 号线单轮 ≥2,500 套、覆盖 ≥60% | 分片/轮转/覆盖看板已交付（P0） | 需 operator 跑 `apply-shards` + 多轮慢扫 |
| 连续 7 天 0 重复推送、误标 <1% | 去重/跳过 suspect 已交付 | 需生产观察 7 天 |
| Top 200 有 ≥3 时段通勤、评分用 p50 | 采样/聚合/评分已交付（P0） | 需生产 `sampling`/`rescore`；SZMC 无时段差异已明确标注 |
| Top 100 7 天后 ≥2 价格点 | 快照写入已交付 | 需时间积累 |
| 看房清单可打勾/拍照/导出 | 已交付（照片为链接，不做上传） | 需人工使用 |
| 外卖 ≥20 条、午/晚两时段 | 探针/详情展示 + `record-probe` 手动录入已交付 | iPhone 真机半自动；样本仍需 operator 采集 |
| Agent 白名单/预算/PII/注入/trace | 已交付；新增原生 tool_calls（默认关闭） | 需生产启用 `APP_AGENT_NATIVE_TOOLS` 后观察 |
| 评测集 ≥50、管理端不写死 | 60 条规则基线 + 真实跑分页 | — |
| 图片标签置信度 + ≥2 信号 | dHash/价格/话术 + OpenCode Go 视觉标签（默认关闭）已交付 | 需 operator 打开 `APP_IMAGE_VISION_ENABLED` 并跑 Top 200 |
| 口碑原文链接 + 置信度 | 证据表/人工确认/评分已交付 | Top 50 证据需人工录入或授权采集 |
| 地图 marker 全真实、无 mock | 真实小区聚合 + 天地图瓦片代理 | 需天地图 Key + 10943 出口 |
| CI 全绿 | 已新增 | 需 GitHub 实际跑一次 |
| 告警/恢复演练 | 告警已交付；恢复脚本已交付 | 演练需 operator 在 Docker/psql 环境执行 |
| 公网看板 token 可撤销/noindex/限流 | 已交付 | 公网前需 TLS/反代；当前不应直接暴露 |
| 无凭据入库/前端 | 保持 | `.env`/`.secrets/` 未读取/未提交 |
| 多源/多城 | 城市/来源管理 + manual + **自如公开列表 API** + 跨源去重 | 58/安居客/豆瓣仍未接入；自如需 operator 启用并跑数据 |
| 开放数据/参考租金 | 表/导入/评分接入 | 无住建局 API Key，需人工导入参考价 |

## 4. 完成度口径

- 计划书 9 个工作流中，W1–W9 的**代码/接口/页面/文档**均已落地；W2/W3/W5/W6 的“数据达标”本质上需要生产运行与人工输入。
- 按“代码可验证交付”计：**约 97%**（剩余为住建局自动取数、58/安居客/豆瓣等更多源，均为可选/需 Key）。
- 按“第 6 节全部验收（含生产数据）”计：**约 80–82%**，因为覆盖率、通勤/价格点、外卖、口碑证据仍依赖生产执行。PR 中如实标注，不把 operator 结果算作 agent 已验证。

## 5. 上线步骤（operator）

1. `cd backend && .venv/bin/alembic upgrade head`（新 head `d4e5f6a7b8c9`）。
2. 在 `.env` 增加 `OPENCODE_GO_API_KEY`（订阅 Key）；`OPENCODE_GO_MODEL=deepseek-v4.1-flash` 已默认。
3. 重启 `rentradar-api / worker / scheduler`；在 `/admin/providers` 用 OpenCode Go 的“测试”按钮确认。
4. 需要原生工具调用时设 `APP_AGENT_NATIVE_TOOLS=true`，先观察 Trace 与工具参数错误率，再长期开启。
5. 备份：在 crontab/systemd timer 跑 `deploy/scripts/backup.sh`；用 `restore-drill.sh` 做一次演练。
6. 分享页：在 `/admin/ops` 创建 token；公网前按 `docs/OPS.md` 加 TLS/反代/限流。
7. 手动导入源：`/admin/ops` 启用 `manual`，在 `/admin/tasks` 新建任务并填 `feed_path`，或 CLI `import-listings`；`ziroom` 源也在 `/admin/ops` 启用后建任务。
8. 参考租金：先人工导入一批（`/admin/ops` 或 CLI），再 `rescore` 观察价格分变化。
