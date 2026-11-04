# 写死 / 非实时数据审计（2026-11-05）

> 结论：当前最主要的问题不是“缺功能”，而是部分数字/条件在入库或前端初始化时写死，页面看起来有值，实际不随公司、需求或数据变化。以下按严重度排序。

## P0：会误导用户，建议先修

| # | 位置 | 现状 | 修复方案 | 工作量 |
|---|---|---|---|---|
| 1 | `backend/app/services/score_service.py` + `listings.score` | 评分在爬取/重算时物化。公司位置变化只同步重算 Top300，后台 `analysis` 默认 2,000 条；预算/户型/电梯变化只筛选不重算；现有 20,743 套未评分 | ①查询时对返回卡片按当前目的地重算；②公司变更后分批全量重算（可恢复/可观测）；③需求变化用用户权重重排，不写回全局分；④给 `listings` 增加 `score_destination`/`scored_at`，前端显示“评分更新中” | 2–3 天 |
| 2 | `backend/app/services/admin_service.py:234` | 管理端漏斗“有图片/AI”恒为 `value:0`，不查 `listing_image_analysis` | 查真实计数；无图片分析时显示“未运行”，有则显示数量 | 0.5 天 |
| 3 | `frontend/src/lib/conditions.ts:22`、`ConditionSheet.vue:10` | 初始条件固定 3500–4500、≤40 分钟、1–2 居、电梯、5 号线沿线，SSE 回来前会误显示；条件面板默认值也会被直接提交 | 改成“未设置/不限/无硬条件”空状态；示例 prompt 保留，但不进真实条件；提交前校验 | 0.5 天 |
| 4 | `frontend/src/features/admin/adminData.ts` | 仍 re-export `@/api/mock/admin` 的 stats/listings/candidates/runs/tasks；页面已改用 empty 数据，但 mock 仍被打包，容易被误用 | 只保留 `money`/`formatTime`，删除 mock re-export；mock 文件仅测试/演示用 | 0.2 天 |
| 5 | `frontend/src/features/admin/TasksView.vue:226` | “任务 2 · 链家”整块写死（未启用、不能操作） | 从任务 API 渲染所有任务；链家只作为“手动来源”说明，不做固定卡片 | 0.5 天 |
| 6 | `backend/app/services/admin_service.py:241-253` | “下一步”文案写死：图片/AI、真实 Agent 运行时、高德、开放数据等，部分已完成或已停用 | 改为由数据状态生成（有/无图片分析、provider 状态、评分覆盖率） | 0.5 天 |
| 7 | `backend/app/services/score_service.py:62/125/187` | 缺价格/通勤/便利样本时固定 0.5 中性分，详情会显示“中性 50%”；用户容易误解为真实分 | 明确标为“数据缺失/不计分”，或按可用权重归一化；前端分项显示“未计分” | 1 天 |

## P1：非实时/不完整，影响搜索质量

| # | 位置 | 现状 | 修复方案 |
|---|---|---|---|
| 8 | `backend/app/services/agent_tools.py:446` | 无通勤条件时 SQL 预截断 100 条再排序；有通勤时全量（已修一半，但无通勤仍可能漏） | 统一用窗口/分页，或按分数+通勤分页；禁止“先截断再过滤” |
| 9 | `backend/app/services/listing_service.py` + `map_service/share_service/watchlist` | 列表/地图/分享/监控都读 `listings.score`，公司或权重变化后不同步 | 统一读“评分版本/目的地”，或查询时按需重算 |
| 10 | `frontend/src/features/admin/AgentMonitorView.vue:354/444` | “48 条条件查询 + 12 条注入”“60 条规则回归集”写死；实际 case 数需从 `agent_eval.json` 读取 | 从 eval 数据计算数量/通过率 |
| 11 | `frontend/src/features/chat/MapPreview.vue` | 未使用的旧组件，写死“5 号线沿线候选” | 删除文件 |
| 12 | `backend/app/services/seed_service.py` | 8 套演示房源/固定租金；仅 CLI seed 使用，生产不自动跑 | 保留但标注 demo；确保生产启动不调用 |

## P2：数据/产品范围，不是代码写死

| # | 项 | 现状 | 决策 |
|---|---|---|---|
| 13 | 详情多图/图片 AI | `listing_images=0`、`listing_image_analysis=0`；只有列表封面 | 需要详情图接口/授权；先把封面大图和视觉分析队列接上 |
| 14 | 外卖/口碑/参考租金 | 6/20、0、0 | 数据验收项，按计划补采/人工导入 |
| 15 | 5 号线/深圳/多城市 | 产品范围固定 | 多城市需单独排期 |

## 建议修复顺序

1. **P0-2/3/4**（半天到一天）：图片统计、前端空状态、移除 mock 死代码——低风险，立刻消除误导。
2. **P0-1/7**（2–4 天）：评分实时化；先做“查询时返回卡片重算 + 显示更新中”，再做全量后台重算。
3. **P0-5/6 + P1-10**（1–2 天）：任务页/下一步/eval 计数改为数据驱动。
4. **P2**：图片、外卖、口碑按数据验收排期。

## 验收口径

- 任意公司位置变化后，卡片评分/通勤理由在 10 秒内与当前目的地一致，或明确显示“评分更新中”。
- 任意预算/户型/条件变化后，结果集合与分项理由可解释；不存在“未评分但仍可被推荐”的卡片。
- 管理端所有数字可追溯到 API 字段；无 `value:0` 硬编码、无 mock re-export。
- 前端首次进入不显示任何未提交的默认预算/通勤/户型。
