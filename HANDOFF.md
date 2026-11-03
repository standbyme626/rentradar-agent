# RentRadar 交接词

> 2026-10-31 03:00 · 给下一个会话/接手人

## 一句话状态

生产采集走 **贝壳 App 列表 v2 API**；`worker`/`scheduler` 运行中，任务 1 `enabled=true`、`filters.transport=api`。房源约 **1395** 套，小区 **587** 个，**824** 套已评分。Phase 0/1/2/3 已完成、Phase 4 LLM Agent 已实调通过；**登录/RBAC/审计、Provider 运行时额度、admin_settings 运行时、监控匹配+飞书推送已接入并实测**；地图/通勤已切 **天地图 + 深圳地铁官方**，高德/滴滴已停用。迁移 head `f1a2b3c4d5e6`，pytest 57 passed。

## 现在有什么

- 鉴权：`/login` 登录页；access JWT（HS256，15 分钟 Cookie）+ refresh（7 天，DB 轮换）；scrypt 密码；admin/viewer；审计表 `audit_log`；除 health/auth 外 API 均需登录，admin API 需 admin；`/docs` 默认关闭。
- 初始管理员：`admin`，密码在 `.secrets/initial-admin.txt`（600）。CLI：`bootstrap-admin`、`create-user`、`set-password`、`list-users`。
- Provider 运行时：`backend/app/services/provider_runtime.py`；天地图 geocode/POI、SZMC 地铁通勤、贝壳 API/CDP、ModelScope chat 全部记账；启用/优先级、熔断、额度硬拦截生效。
- 地图/通勤：**高德、滴滴 MCP 已 disabled**；天地图（约 10/10000）负责地理编码/POI；SZMC（零额度）负责地铁+步行；旧 AMAP 通勤样本按 1 天阈值逐步重采。
- 额度：高德预置 900/5000（已停用）；ModelScope 7/500；贝壳按日计数不封顶。
- 设置运行时：`admin_settings` 已接通知阈值、静默、批量上限、AI/高德上限、暂停告警、监控推送；设置页保存即生效。
- 监控：`agent_monitor_matches`；scheduler 每 5 分钟入队 `monitor_match`，worker 匹配新上架/重新上架/降价，静默时只累积 pending，结束后按批推飞书。
- 地图/通勤：天地图正向地理编码 + POI 周边；SZMC 官方站点字典 + MinTimeJson（地铁+步行）；高德/滴滴 disabled。
- 采集：贝壳 App API 主通道，CDP 保留兜底；快扫 30 分钟 1 页，慢扫 360 分钟 30 页，09:00 日报。
- 数据：5 号线 `total≈6689`；API 新增 179 套；30 页慢扫 900 条、去重 180、suspect 自动跳过（未误标）。
- 坐标：App API 列表自带 GCJ-02 坐标，已把有坐标小区从 254 补到 457，未消耗高德额度。
- POI/通勤：248 个小区有样本（高德），285 条通勤样本；新坐标小区尚未补，只能按 Top 候选小批量 enrich。
- 前端：Vue 3 + Vite，用户端 `/`、管理端 `/admin`；`frontend/.env` 分域开关已全部关闭 mock：用户端 Agent 真实、管理端真实。
- 管理端：`/admin/overview|candidates|commute|quality|providers|agent|images|tasks|logs|settings` 已接真实 `/api/admin/*`；Agent 页读取真实会话。
- 用户端：`POST /api/agent/messages/stream` SSE；LLM（魔搭 DeepSeek V4.1 Flash）解析意图 + 生成回答，失败自动回退规则版；会话和监控存库（当前 6 个会话、1 个监控）。
- AI Provider：`/admin/providers` 的 AI 域显示“魔搭 DeepSeek V4.1 Flash”，已配置；Provider 测试约 1s，额度/调用日志可查。
- API 管理：`/admin/providers` 始终读取真实后端，按域展示 provider 健康、额度、测试结果和调用日志。
- 原型：`http://192.168.31.197:8011/`（`prototype/user-v2.html`、`admin-v2.html`，LAN only）。
- 备份：`bash deploy/scripts/backup.sh` → `/home/kkk/backups/rentradar/`。

## 关键路径

| 项 | 路径 |
|---|---|
| 项目根 | `/home/kkk/Project/rentradar` |
| 项目记忆 | `MEMORY.md` |
| 新采集源 | `backend/app/sources/beike_api.py` |
| 采集编排 | `backend/app/services/crawl_service.py` |
| Provider 框架 | `backend/app/integrations/`（base/registry/housing/maps） |
| Provider 管理 API | `backend/app/api/routes/admin_providers.py`、`services/provider_service.py` |
| Admin BFF | `backend/app/api/routes/admin.py`、`services/admin_service.py`、`schemas/admin.py` |
| Agent SSE | `backend/app/api/routes/agent.py`、`services/agent_service.py`、`schemas/agent.py` |
| Agent LLM | `backend/app/integrations/ai/modelscope.py`、`services/llm_service.py` |
| 鉴权/审计 | `backend/app/core/security.py`、`core/rate_limit.py`、`api/routes/auth.py`、`services/auth_service.py`、`schemas/auth.py` |
| Provider 运行时 | `backend/app/services/provider_runtime.py` |
| 天地图 | `backend/app/integrations/maps/tianditu.py` |
| 深圳地铁 | `backend/app/integrations/transit/szmc.py` |
| 设置运行时 | `backend/app/services/settings_service.py` |
| 监控匹配 | `backend/app/services/monitor_service.py`、`workers/scheduler.py`、`workers/worker.py` |
| 新迁移 | `backend/alembic/versions/f1a2b3c4d5e6_auth_quota_monitor.py` |
| Agent 表 | `backend/alembic/versions/d5e6f7a8b9c0_agent_sessions.py`、`e6f7a8b9c0d1_agent_llm_trace.py` |
| Provider 管理页 | `frontend/src/features/admin/ProvidersView.vue` |
| 管理端 mock 开关 | `frontend/.env`（gitignored）、`.env.example` |
| Provider 迁移 | `backend/alembic/versions/b7e4c2a9f1d3_provider_management.py` |
| 旧 CDP 源 | `backend/app/sources/cdp.py`、`beike.py` |
| 前端 | `frontend/src/`（Vue3 + Vite + Tailwind） |
| 接口清单 | `docs/API-SOURCES.md` |
| 服务单元 | `deploy/systemd/rentradar-{api,worker,scheduler}.service` |
| 凭据 | `.env`（600）、`.secrets/feishu-app.json`（600）；**不要提交/输出** |

## 本次改动（2026-10-30 / 10-31）

- 新增 `BeikeAPIFetcher`：调用 `Rentplat/v2/house/list`，解析坐标、调价、上架时间、楼层、标签、封面图。
- **翻页必须回传上一页 `data.feed_query_id`**；不回传时 `offset` 0/30/60 可能返回同一批。
- `run_task` 新增 `transport=api|cdp`（任务 1 现为 `api`）；CLI 新增 `--transport`。
- 同一轮按 `house_code` 去重；`house_code` 与 CDP 的 `data-house_code` 一致，旧房源直接更新。
- App API 列表坐标回填小区坐标（`geocode_confidence=0.9`），省高德调用。
- API 未抓全（`total > pages×30`）时跳过 `suspect` 判定，避免把未抓到的房源误标下架。
- 新增 `app/integrations/` provider 框架、registry、额度/健康/调用审计表；Alembic `b7e4c2a9f1d3`。
- 适配贝壳 API/CDP、高德；新增天地图（固定 10943）和滴滴 MCP（默认沙箱，不提供下单方法）。
- 新增 `/api/admin/providers*` 和 `/admin/providers` 页面；SPA fallback 对 `/api/*` 返回 JSON 404。
- Phase 2 新增 `/api/admin/{overview,candidates,coverage,quality,runs,tasks,settings,agent/sessions}` 和 `/api/admin/jobs/*`、`/api/admin/tasks/{id}/run`。
- 管理端切真实数据；新增分域 mock 开关；总览/候选/质量/任务/设置/日志/API 管理均读真实库。
- worker 新增 `analysis`（本地重评分）、`geocode`（指定小区 enrich）、`sampling`（单次采样）处理；`analysis`/`sampling` 仍是 Phase 2 简化版。
- Phase 3 新增 `agent_sessions`/`agent_monitors` 表；`/api/agent/messages/stream` SSE、sessions/monitors 接口。
- 规则版 Agent：解析预算/通勤/户型/区域/电梯 → 查本地评分房源 → 条件事件/计划/卡片/回答；追问支持预算/通勤/户型/区域、对比、保存监控、图片占位。
- 用户端聊天切真实后端；管理端 Agent 页读取真实会话；条件 chips 由 SSE `conditions` 事件更新。
- Phase 4 新增 ModelScope `modelscope_deepseek` Provider（AI domain）和 `llm_service`：LLM 解析预算/通勤/户型/区域/电梯 + 生成回答；规则版作为 fallback。
- `agent_sessions` 新增 `model/prompt_tokens/completion_tokens/cost/llm_fallback`，管理端 Trace 显示模型与 token。
- ModelScope Key 从本机 `/root/.credentials/modelscope.env` 复制到项目 `.env`（600）；provider 测试通过；业务 LLM 调用回写 `provider_usage`/`provider_calls`。
- 实测对话：`deepseek-ai/DeepSeek-V4.1-Flash-1017`，4.3–4.5s，tokens 745/513，fallback=false；Provider 用量 3/2000（含测试）。
- 测试：`57 passed`、ruff 全绿、前端构建通过；provider 7 个；登录页、管理端、用户端、监控抽屉均用 Playwright 验证。

## P0 收口（2026-11-04）

已完成（代码 + 本地检查）：

- **W1 分片覆盖**：`python -m app.cli shards --line 5号线 --probe` 生成/校验 `li110460696s<站点id>` 分片；`apply-shards --task-id 1 --line 5号线` 写入任务 filters 并把快/慢扫设为 10/180 分钟；scheduler 慢扫每次轮转一个站点分片，`/api/admin/crawl-coverage` + 管理端「采集任务」页显示每站已抓/total/库内/完整状态。
- **W2 通勤 p50/p90**：迁移 `a1b2c3d4e5f6` 给 `commute_samples` 加 `depart_bucket/direction`；enrich/sampling 按 4 时段采样，评分用 p50，详情显示 p50/p90/样本数；管理端通勤页改 SZMC 零额度口径。
- **W3 详情/台账**：详情抽屉接 `/api/listings/{id}`（真实评分拆解、价格快照、通勤、外卖、检查）；新增 `GET /api/listings/watchlist`、`GET /api/listings/watchlist/export.csv`；用户端「看房清单」抽屉支持状态流转、检查项、备注、照片链接、CSV。
- 测试：`pytest -q` 82 passed；`ruff check app tests` 全绿；`npm run build` 通过；`alembic heads` = `a1b2c3d4e5f6`。
- UI 证据：`docs/evidence/p0-ui/`（before 来自 main，after 来自当前分支；两边都用同一本地 mock API，非生产数据）。

生产执行（agent 没有生产库权限，未执行）：

1. `cd backend && .venv/bin/alembic upgrade head`（操作员执行迁移）。
2. `.venv/bin/python -m app.cli apply-shards --task-id 1 --line 5号线`
3. 需要时在 `/admin/commute` 提交 Top 候选采样，或 `.venv/bin/python -m app.cli rescore --task-id 1 --limit 2000` 让旧房源写入 p50/components。
4. 等慢扫轮转完 37 个分片后看 `/admin/tasks` 的覆盖看板；覆盖率 ≥60% 是数据验收，不在本次代码交付内。

注意：SZMC `MinTimeJson` 无出发时间参数，4 时段结果相同（`static=true`），p90 不是实时拥堵；详情/清单不要写成“实时实测”。

## 待办（按优先级）

1. **Agent 工具运行时 + 护栏**：LLM tool calling、白名单、参数校验、PII/prompt injection、预算硬停、trace/eval。
2. **更全的 5 号线覆盖**：API 单条件最多 3000 条；按商圈/站点拆分条件、多轮合并；当前 1096 套 / total 约 6300。
3. **图片/AI**：images 表、详情图、pHash、Qwen-VL 标签、假房源信号。
4. **通勤 p50/p90**：SZMC 已接单次地铁+步行；下一步补 4 时段 × 工作日 p50/p90，并逐步替换旧 AMAP 反向样本。
5. **地铁/公交、开放数据**：住建局参考租金、公交静态、风险图层。
6. **前端补齐**：地图真实数据、看房清单/台账 UI、价格历史真实曲线。
7. **运维**：CI、告警、恢复演练；公网暴露前加 TLS/反代/限流。

## 常用命令

```bash
cd /home/kkk/Project/rentradar
make db / migrate / seed / api / web / worker / scheduler / backup
curl http://192.168.31.197:8010/health
systemctl is-active rentradar-api rentradar-worker rentradar-scheduler

cd backend
.venv/bin/python -m app.cli bootstrap-admin --username admin
.venv/bin/python -m app.cli create-user --username friend --role viewer
.venv/bin/python -m app.cli set-password --username admin
.venv/bin/python -m app.cli list-users
.venv/bin/python -m app.cli crawl --task-id 1 --pages 1 --sort newest --line li110460696 --transport api
.venv/bin/python -m app.cli crawl --task-id 1 --pages 1 --transport cdp   # 兜底，需先过验证码
.venv/bin/python -m app.cli shards --line 5号线 --stations 20 --probe   # 站点分片 total/去重校验
.venv/bin/python -m app.cli enrich --task-id 1 --limit 50
.venv/bin/python -m app.cli rescore --task-id 1 --limit 2000
.venv/bin/python -m app.cli digest --dry-run
.venv/bin/python -m app.cli probe --community-id 1 --no-navigate
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests
curl -s http://192.168.31.197:8010/api/admin/providers
curl -s -X POST http://192.168.31.197:8010/api/admin/providers/tianditu/test
curl -s http://192.168.31.197:8010/api/admin/overview
curl -s http://192.168.31.197:8010/api/admin/settings
curl -s http://192.168.31.197:8010/api/agent/sessions
curl -s -X POST http://192.168.31.197:8010/api/admin/providers/modelscope_deepseek/test
curl -sN -X POST http://192.168.31.197:8010/api/agent/messages/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"会展中心，预算4000，5号线，通勤40分钟内"}'
```

## 已知故障与急救

| 现象 | 处理 |
|---|---|
| App API 403/412 或验证页 | 已自动抛 `CaptchaRequiredError` 并把任务置 `enabled=false`；改用 CDP 前需在 Windows Chrome 手动过验证 |
| App API 每页重复 | 检查请求是否带上一页 `data.feed_query_id` |
| 天地图 403 IP 不匹配 | Key 必须走 `socks5h://127.0.0.1:10943`；`TIANDITU_PROXY` 已设置 |
| 天地图公交超时 | 已知：transit 接口经 10943 出口超时；通勤用 SZMC，不要等天地图公交 |
| SZMC 通勤为空 | 小区 3km 内无地铁站会返回空；这是预期，不回落高德 |
| 滴滴 MCP 估价 | 默认沙箱；真实估价把 `DIDI_MCP_URL` 换成 `/mcp-servers`，禁止调用下单方法 |
| 未实现 API 返回 HTML | 已修：`/api/*` 未匹配返回 JSON 404；如仍见 HTML，重启 `rentradar-api` |
| 管理端数据没变 | 检查 `frontend/.env` 的 `VITE_USE_MOCK_ADMIN`；改完需 `npm run build` |
| 登录后立刻 401 / 反复跳登录 | 检查浏览器是否带 `rr_access`/`rr_refresh` Cookie；确认 `APP_SECRET_KEY` 未变；必要时 `set-password` 后重登 |
| 忘记管理员密码 | `python -m app.cli set-password --username admin` |
| Provider 显示停用/额度不足 | 看 `/admin/providers` 的 enabled/priority 与额度；AMAP 当前预置 900/5000，超额调用会被前置拦截 |
| 监控没有推送 | 检查 `admin_settings.monitorPush`、`feishu`、静默时段；pending 会保留，结束后再推 |
| analysis/sampling 任务结果只有重评分/单次采样 | Phase 2 简化版；详情/AI/p50/p90 在后续阶段 |
| 聊天没有卡片 | 看 `/api/agent/messages/stream` 是否 200、`agent_sessions.result`、后端日志；规则版只查本地库存 |
| 魔搭 Provider 显示未配置 | `.env` 缺 `MODELSCOPE_API_KEY`；Key 来源 `/root/.credentials/modelscope.env`，加完重启 `rentradar-api` |
| 魔搭 401/429 | 401 = Key 无效；429 = 额度/单模型限流；Agent 会自动回退规则版 |
| 魔搭返回空 content | V4.1F 是推理模型，`reasoning_content` 可能占满 token；当前 parse 1200 / answer 900，勿调太小 |
| 模型页显示 SupportApiInference=false | 以 `/v1/models` 和真实 chat 为准；`-1017` 已实测可用 |
| 监控保存后没有推送 | 看 `admin_settings.monitorPush`、`feishu`、静默时段；pending 会保留，静默结束后按批推送 |
| 采集 0 条 | 看 `runs.error`、`journalctl -u rentradar-worker`、任务 filters 的 `line/transport` |
| 慢扫 suspect 未产生 | 正常：API 未覆盖全量时主动跳过，避免误标 |
| 高德额度告急 | 已停用高德；地图走天地图，通勤走 SZMC。需要恢复时在 `/admin/providers` 重新启用 |
| iPhone 截屏/点击失败 | `systemctl restart usbmuxd iph-daemon`，等 6s，`ipctl ping` |
| 百度 AK 210 | 必须走 tx43 出口（`BAIDU_PROXY=socks5h://127.0.0.1:10943`） |
| Vite 代理指向旧地址 | 确认没有生成的 `vite.config.js` |

## 不要做

- 不要对全部小区跑 `enrich`：高德个人 Key 每月约 5000 次。
- 不要直接把 8010 暴露公网：已启用登录/RBAC，但仍需 TLS/反向代理/限流；当前 Cookie Secure=false，仅适合 LAN HTTP。
- 不要自动抓链家：robots 全站 Disallow。
- 不要在没有验证的情况下把 `suspect` 改成 `gone`。
- 不要把 API Key 写进数据库或前端；provider 页面只显示 configured 状态。
- 不要调用滴滴 MCP 的下单工具；只允许搜索、路线和估价。
- 不要提交 `.env`、`.secrets/`、`data/`、`node_modules/`、`dist/`。
- Agent 还没有完整 LLM 工具运行时；当前 LLM 只做意图解析和回答，查询仍是本地确定性工具。
- 不要把规则版回答描述成“模型已规划/图片分析已完成”；Trace 里有 model/tokens/fallback 可核对。
- 不要使用 OpenRouter 收费模型。
- 不要 `git reset/clean` 清掉未提交改动。
- 不要不带 `feed_query_id` 翻页，也不要盲目把 `slow_pages` 调大来“抓全”。

## 验收

- `curl http://192.168.31.197:8010/health` → `status: ok`
- `systemctl is-active rentradar-api rentradar-worker rentradar-scheduler` → 三个 active
- 任务 1：`filters.transport=api`、`line=li110460696`、`fast_pages=1`、`slow_pages=30`、`enabled=true`
- `pytest -q` → 57 passed；`ruff check app tests` 全绿
- `/admin/providers` 可打开，7 个 provider 显示健康/额度/测试结果；天地图约 13/10000、SZMC 约 6 次、高德 900/5000（disabled）、ModelScope 7/500
- `/admin/overview`、`/admin/candidates`、`/admin/quality`、`/admin/tasks`、`/admin/settings` 显示真实数据
- `/admin/agent` 显示真实 Agent 会话；Trace 可打开，显示模型/tokens/cost
- 用户端 `/` 发一句话能返回真实房源卡、计划、条件 chips；追问/保存监控可用
- 未配置魔搭 Key 或额度耗尽时 Agent 自动回退规则版；现已配置并实测 `deepseek-ai/DeepSeek-V4.1-Flash-1017`
- 实测 LLM 会话：model=DeepSeek-V4.1-Flash-1017、tokens 745/513、fallback=false、约 4.5s
- Provider 用量：`modelscope_deepseek` 7/500（受 aiDailyCap 约束）、`tianditu` 约 13/10000、`szmc` 约 6 次、`amap` 900/5000（disabled）、`beike_api` 按日计数
- 登录：匿名 admin API 401；viewer 403；admin 200；`/docs` 404
- 额度：AI 日上限 0 时规则版回退且用量不增；AMAP 上限 900 时设置接口 400 且无外部调用
- 监控：测试监控扫描 2 天事件 711 条 pending，静默时未发送
- 管理端设置 PUT 后写入 `app_settings.admin_settings`
- 最近慢扫：30 页 / 900 条 / 新增 148 / 去重 180 / `suspect_skipped=true`


---

## 2026-11-04 · P1 补记（Agent 工具运行时 / 封面 / 口碑 / 地图）

- **迁移**：head `b2c3d4e5f6a7`，新增 `agent_tool_calls`、`listing_images`、`listing_image_analysis`、`reputation_mentions`、`agent_eval_runs`，`agent_sessions.guardrails`。
- **Agent**：`agent_tools.py` 白名单 5 个只读工具 + `save_monitor` 写工具（仅显式“保存/监控”路径）；`llm_service.plan_tools` 严格 JSON 计划，失败回退 `rule_plan`；`guardrails.py` 预算硬停/PII/注入；每次调用落 trace；`agent_eval_service.py` 60 条黄金集（48 查询 + 12 护栏），`POST /api/admin/agent/eval/run` 零外部调用。
- **图片**：`image_service.py` 下载贝壳列表封面到 `APP_IMAGE_CACHE_DIR`，dHash + 重复/低价/话术信号，≥2 信号才可疑；`image_analysis` job；管理端“图片 / AI”读真实队列与重复组。视觉模型未授权，标签标记“待视觉”。
- **口碑**：`reputation_service.py` + 管理端“口碑证据”页；人工录入/抽取草稿/确认/排除；评分第 5 项改为真实聚合，无证据显示“数据不足（中性分）”。抽取调用 ModelScope 文本模型，默认草稿 uncertain。
- **地图**：`map_service.py` 输出 WGS-84 小区坐标/中位租金/评分/通勤 p50；Tianditu `fetch_tile` + 服务端磁盘缓存；前端 `MapPanel.vue` 自研墨卡托瓦片渲染 + marker/筛选/详情入口；无 Key 时降级坐标网格。调研见 `docs/TIANDITU-MAP.md`。
- **验证**：`pytest -q` 119 passed；`ruff check app tests` 全绿；`npm run build` 通过。UI 证据同样使用本地 mock API（agent 无生产库权限），见 `docs/evidence/p1-ui/`。
- **仍需真实环境验证**：天地图瓦片需要有效 Key + 10943 出口；真实 rescore 需在生产库跑 `rescore` 才会把新口碑分写入 `score_reasons`；图片下载依赖贝壳 CDN 可达。
