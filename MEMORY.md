# RentRadar 项目记忆

> 2026-10-31 03:45：地图/通勤已切到天地图 + 深圳地铁官方：Tianditu 负责地理编码/POI，SZMC 负责地铁+步行通勤；**高德与滴滴 MCP 已停用**。登录/RBAC/审计、Provider 额度、设置运行时、监控推送均已接；迁移 head `f1a2b3c4d5e6`；pytest 57 passed。初始管理员凭据在 `.secrets/initial-admin.txt`（600），登录页 `/login`。房源约 1395 套、824 套已评分。新会话先看 `HANDOFF.md`。
> 项目根：`/home/kkk/Project/rentradar`；文档：`docs/PROJECT.md`、`docs/DEVELOPMENT.md`、**`docs/API-SOURCES.md`（外部接口/数据源清单，2026-10-30）**；参考项目：`reference/ai-goofish-monitor`（gitignored）。


> **P0 收口（2026-11-04）**：W1 站点分片覆盖（planner/probe/apply-shards/scheduler 轮转/覆盖看板）、W2 通勤 `depart_bucket` + p50/p90、W3 详情真实数据 + 看房清单（状态/检查项/备注/照片链接/CSV 导出）已实现。迁移 head `a1b2c3d4e5f6`；pytest 82 passed；前端构建通过。生产数据验收仍需执行迁移、`apply-shards`、`sampling`/`rescore`，详见 `HANDOFF.md`。

## 运行形态

| 组件 | 说明 | 端口/地址 |
|---|---|---|
| Postgres | 容器 `rentradar-postgres`，`deploy/docker-compose.yml`，`restart: unless-stopped` | `127.0.0.1:5433` |
| API | systemd `rentradar-api`（enabled），绑定局域网 IP；**已启用登录/RBAC**，LAN only | `http://192.168.31.197:8010` |
| Worker | systemd `rentradar-worker`（enabled），`SKIP LOCKED` 消费 jobs | — |
| Scheduler | systemd `rentradar-scheduler`（enabled），快 10min / 慢 180min / 09:00 日报 | — |
| 前端 dev | 临时 unit `rentradar-web`（未 enable），Vite 绑 127.0.0.1；/api 代理到 8010 | `http://127.0.0.1:5173` |
| 生产 SPA | `npm run build` 后由 FastAPI 托管 `/`（SPA fallback） | `8010` |

## 原型（2026-10-29 17:20）

- `prototype/index.html`：入口页；`prototype/user-v2.html`：新版用户端（一句话 → 对话 + 结果画布）；`prototype/admin-v2.html`：新版管理端（数据质量 + 候选工作台 + 预算 + Agent 监控：会话/Trace、评测反馈、成本护栏、版本告警）。
- 旧版 `user.html` / `admin.html` 保留作对比；独立 HTML，内嵌当前库真实房源/统计；图片/AI 为设计占位。
- 静态端口：`http://192.168.31.197:8011/`（systemd 单元 `rentradar-prototype`，LAN only）。
- 同步副本：`/home/kkk/Sync/downloads-kkk/RentRadar-{原型入口,用户端-v2,管理端-v2}.html`（Windows 可直接打开）。

## 前端（2026-10-31）

- 技术栈：Vue 3.5 + Vite 6 + TS 5.7 + Tailwind 3.4 + Pinia + Vue Router + lucide-vue-next；基础 UI 件自建，未引入 shadcn-vue。
- 路由：`/` 用户端（一句话 → 对话 + 结果画布）；`/admin` 管理端（总览/候选/通勤预算/数据质量/API 管理/Agent 监控/图片 AI/任务/日志/设置）。
- 数据层：`src/api/contracts.ts` 类型 + `services/{agent,admin,providers}.ts` + `http.ts`（REST + SSE）；分域 mock 已全部关闭：`VITE_USE_MOCK_AGENT=false`、`VITE_USE_MOCK_ADMIN=false`；本地 `frontend/.env` 已创建且 gitignored。
- 已实现后端：`/api/agent/messages/stream`（SSE）、`/api/agent/sessions`、`/api/agent/monitors`；`/api/admin/{overview,candidates,coverage,quality,runs,tasks,settings,agent/sessions}`、`/api/admin/jobs/*`、`/api/admin/tasks/{id}/run`。
- 用户端聊天：规则版 Agent 解析预算/通勤/户型/区域/电梯等，查本地库存出 4 张真实卡；追问支持预算/通勤/户型/区域、对比、保存监控、图片占位；条件 chips 由 `conditions` SSE 事件更新。
- Agent 会话/监控：`agent_sessions`、`agent_monitors` 表；当前 **6 个会话、1 个监控**；管理端 Agent 页读取真实会话，评测/成本页仍是设计预览。
- LLM：Provider `modelscope_deepseek`（AI domain），模型 `deepseek-ai/DeepSeek-V4.1-Flash-1017`；`llm_service` 用 LLM 解析意图 + 生成回答，失败/无 Key 自动回退规则版；session 记录 model/tokens/cost/fallback。
- ModelScope Key 已配置（来源 `/root/.credentials/modelscope.env`，已复制到项目 `.env`，600）；Provider 测试通过；真实对话约 4.3–4.5s，tokens 约 745/513；免费额度账号 2000 次/天、单模型约 500 次/天；当前用量 5/2000。
- 业务 LLM 调用会写回 `provider_usage`/`provider_calls`（capability=chat），Provider 页额度与日志可见。
- 地图：天地图 geocode/POI；通勤：SZMC 官方 MinTimeJson；高德与滴滴当前 disabled。
- **鉴权（2026-10-31）**：`/login` 登录页；access JWT HS256 Cookie 15 分钟 + refresh 7 天（`rr_access`/`rr_refresh`，httpOnly、SameSite=Lax）；密码 scrypt；角色 admin/viewer；`users`/`auth_sessions`/`audit_log`；除 `/health`、`/api/auth/*` 外全部 API 需登录，`/api/admin/*` 需 admin；`/docs`、`/openapi.json` 默认关闭。
- 初始管理员：`admin`，凭据在 `.secrets/initial-admin.txt`（600，gitignored）；CLI：`bootstrap-admin`、`create-user`、`set-password`、`list-users`。
- **Provider 运行时（2026-10-31）**：`app/services/provider_runtime.py`；AMAP 地理编码/POI/通勤、贝壳 API/CDP、ModelScope chat 全部走运行时；每次调用写 `provider_calls`/`provider_usage`，读取 `provider_settings` 的 enabled/priority；失败 3 次熔断 5 分钟；额度不足在调用前拦截。
- 额度：AMAP 已按交接估算预置 900/5000（本机 `provider_usage`，后续精确累加）；ModelScope 当前 7/500（受 `aiDailyCap` 约束）；Beike 按日计数但不封顶。
- `admin_settings` 运行时已生效：`amapMonthlyCap`、`aiDailyCap`、`batchCap`、`sessionAmapCap`（Agent 当前不调 AMAP，只在预算事件里展示）、`notifyBatchCap`、`notifyScoreMin`、`priceDropPct`、`quietStart/End`、`feishu`、`digest`、`quiet`、`pauseAlert`、`monitorPush`。
- **监控匹配（2026-10-31）**：`agent_monitor_matches` 表；scheduler 每 5 分钟入队 `monitor_match`，worker 扫描新上架/重新上架/降价，按条件 + 通勤匹配，去重后写 pending；静默时段只入库不推送，非静默按 `notifyBatchCap` 分组推飞书并更新 `new_matches`。快速验证产生 711 条匹配（测试监控已删）。
- 用户端已有本地持久化：历史需求/我的监控（localStorage）；地图可选 `VITE_AMAP_JS_KEY`，未配置时显示占位。
- 详情抽屉（2026-11-04）：打开时拉 `/api/listings/{id}`，显示真实评分拆解（`score_reasons.components`）、价格快照、通勤 p50/p90、外卖实测、看房检查；不再写死 35/25/13/8/5/5 或假 sparkline。看房清单抽屉：状态/检查项/备注/照片链接/CSV 导出。
- 构建：`cd frontend && npm run build`；FastAPI 8010 托管 `frontend/dist`，直接访问 `http://192.168.31.197:8010/`、`/admin`。Dev：`npm run dev`（127.0.0.1:5173）；环境变量样例 `frontend/.env.example`。
- 旧 `src/views`/`src/layouts` 已从 tsconfig 排除、保留未删；新页面在 `src/features/chat`、`src/features/admin`。

## API 管理（2026-10-31）

- 后端 `backend/app/integrations/`：`base`（ProviderMeta/Capability/QuotaPolicy）、`registry`、`housing/{beike_api,beike_cdp}`、`maps/{amap,tianditu,didi_mcp}`、`transit/szmc`。
- 数据表：`provider_settings`、`provider_usage`、`provider_health`、`provider_calls`；Alembic `b7e4c2a9f1d3`。
- 管理接口：`GET /api/admin/providers`、`GET/PATCH /api/admin/providers/{code}`、`POST .../test`、`GET .../usage`、`GET /api/admin/provider-calls`。
- 管理页 `/admin/providers`：按房源/地图/地铁公交/开放数据/口碑/AI/通知分域；显示健康、额度、代理、测试结果、调用日志。
- Phase 2 BFF：`/api/admin/overview|candidates|coverage|quality|runs|tasks|settings|agent/sessions`；jobs：`analysis`（本地重评分）、`geocode`（指定小区 enrich）、`sampling`（单次采样，p50/p90 待接入）。
- Phase 3 Agent：`/api/agent/messages/stream`、`/sessions`、`/monitors`；表 `agent_sessions`、`agent_monitors`，Alembic `d5e6f7a8b9c0`。规则版 Agent，不调用 LLM；详情/AI 仍为 pending。
- Phase 4 LLM：`app/integrations/ai/modelscope.py`、`services/llm_service.py`；Alembic `e6f7a8b9c0d1` 增加 model/tokens/cost/llm_fallback。模型 ID 必须用 `deepseek-ai/DeepSeek-V4.1-Flash-1017`。
- ModelScope Key 未配置：provider 显示“未配置”，Agent 自动回退规则版；配置 `MODELSCOPE_API_KEY=ms-...` 后重启 API 生效。
- 天地图固定走 `socks5h://127.0.0.1:10943`（Key 绑定该出口）；已接正向地理编码与 POI 周边。天地图 transit 接口经该出口超时，未接入。
- 深圳地铁官方 `MinTimeJson` + `shentie.json` 站点字典已接为 `szmc` provider；地铁+步行时长，零额度。
- 滴滴 MCP 默认沙箱，provider 只暴露搜索/路线/估价，不提供下单方法；当前已停用，避免沙箱路线污染通勤。
- 启用/优先级由 `provider_runtime` 在运行时读取；高德与滴滴已停用，地图调用优先天地图，通勤优先 SZMC。
- 地图/通勤已接；未实现域：开放数据、口碑、图片/AI；页面显示 0 / 待接入。

## 数据（2026-10-31 02:00）

- 房源 1395 套，824 套通过硬过滤并评分；5 号线 scope 约 1100+ 套。
- 587 个小区，约 460 个有坐标；250 个有通勤样本；通勤样本 287 条。
- 154 套活跃房源缺坐标、903 套缺通勤；170 个小区餐饮 POI 封顶（≥600）。
- 新坐标小区尚未补 POI/通勤，按候选优先补，禁止全量 enrich。
- 通勤起点为深圳会展中心（example=false）；新样本由 SZMC 生成（地铁+步行，provider=szmc），旧 AMAP 样本按 1 天阈值逐步重采。
- 口碑仍为中性 0.5；通勤已按 4 个 `depart_bucket` 采样并聚合 p50/p90；SZMC 为时刻表最短耗时，同 OD 不同时段结果相同（不等于实时拥堵）。
- 外卖实测 5 条（全部夜宵时段，address_label 常缺失，confidence 0.5）。

## 采集

- **主源（2026-10-30 起）**：贝壳 App 列表 v2 `https://app.api.ke.com/Rentplat/v2/house/list`，免登录免签名；实现 `backend/app/sources/beike_api.py`，任务 1 `filters.transport=api`。
- 请求：`city_id=440300`、`condition=li110460696/rco11`、`offset<=2999`、`limit<=30`；**翻页必须回传上一页 `data.feed_query_id`**，否则 offset 无效/大量重复。
- 列表返回坐标（GCJ-02）、调价、上架时间、标签、封面图；`house_code` 与 CDP 的 `data-house_code` 一致，可直接更新旧房源。
- 5 号线 `total≈6689`，单轮 30 页仅覆盖 900 条；结果有随机性，按 `house_code` 去重。
- 小区坐标优先用列表 `geolatitudelongitude` 回填（置信度 0.9），没有坐标才走高德。
- CDP 兜底：受控 Windows Chrome `127.0.0.1:9333` → SSH 隧道 `boss-cdp-tunnel` → Windows `C:\Chrome-debug`；整轮复用同一标签页、6-12s 间隔，检测人机验证立即中止并置 `enabled=false`。
- 链家 robots 全站 Disallow，不自动抓，只保留手动链接。
- 命令：`python -m app.cli crawl --task-id 1 --pages 1 --sort newest --line li110460696 --transport api`
- 分片覆盖（2026-11-04，P0/W1 第一步）：`python -m app.cli shards --line 5号线 --probe` 从筛选字典生成站点条件，探测每站 total 与跨站去重；`--pages 0` 自动抓全，`--json` 输出计划。当前只生成逐站 crawl 命令，尚未接入 scheduler。
- 全量扫描按 `listing.raw.scope` 过滤；API 未覆盖全量（total > pages×30）时**跳过 suspect 判定**，避免误标。
- 冷启动：首次运行 `baseline=True`，new 事件 `notified=True`，不推送；UI 显示「基线」。

## 调度/通知

- 快扫 30 分钟 1 页；慢扫 360 分钟 30 页（`full_scan`，API 通道单轮 900 条）；09:00 日报。
- **worker/scheduler 已于 2026-10-30 恢复运行，任务 1 `enabled=true`、`transport=api`**；CDP 通道保留，仅在需要时手动启用。
- 即时通知：阈值/每轮条数/静默时段均从 `admin_settings` 读取（默认新上架 ≥75、降价 ≥8%、每轮 10 条、23:00-08:00 静默）。
- 监控推送：scheduler 每 5 分钟入队 `monitor_match`；静默时只累积 pending，结束后按批推飞书。
- 连续两次全量未出现 → `suspect`（仅 CDP/完整覆盖时；API 未抓全时自动跳过），**不自动 gone**。
- 连续 3 次运行失败 → scheduler 熔断跳过该任务。
- 备份：`bash deploy/scripts/backup.sh` → `/home/kkk/backups/rentradar/`，保留 7 天。

## 评分

- 性价比：同小区同户型 30 天中位价，样本不足回落到同区同户型。
- 通勤：小区 → 公司，SZMC 时刻表最短耗时；按 07:30/08:00/08:30/09:00 四个 `depart_bucket` 采样，评分取 p50，详情显示 p90 和样本数；`static=true` 表示时段无波动，不冒充实时。通勤目的地址存 `app_settings.commute_destination`，**当前是「深圳会展中心」（example=false）**。
- **高德个人 Key 每月约 5000 次**：运行时已按 `amapMonthlyCap` 硬拦截，且已预置 900 次；禁止对全部小区批量 enrich；只对 Top 候选小区补样本，优先复用缓存。一次 498 小区全量 enrich 约 2500+ 次调用。
- 便利：高德 1km 餐饮/便利店/超市/菜场 POI，对数归一化。
- 条件/新鲜度保留；口碑中性。每条分数都有 `score_reasons`。

## 外卖探针

- iPhone 11 Pro USB 接入；`iph-daemon` 可用；USB 抖动时 `systemctl restart usbmuxd iph-daemon` 可恢复。
- 虚拟定位：`pymobiledevice3 developer dvt simulate-location set <lat> <lng>`，进程需保持 stdin 打开；`LocationSession` 负责持有/clear。Apple 地图已验证生效。
- 美团权限：必须「使用 App 期间 + 精确位置」；权限已设好。
- 半自动探针（要求美团停在外卖首页）：`python -m app.cli probe --community-id <id> --no-navigate`
- 全自动导航未稳定：商家详情页返回键/控件树会卡；`pkill imeituan` + 桌面第 2 页图标冷启动可回首页，但仍偶发落商家页。
- 详情页已展示「外卖实测」；截图在 `data/probes/`（gitignored，含手机画面，勿公开）。

## 凭据（勿外泄）

- `.env`（600，gitignored）：飞书 App ID/Secret/open_id、AMAP_WEB_KEY、BAIDU_AK、BAIDU_PROXY。
- `.secrets/feishu-app.json`（600，gitignored）：飞书应用凭据。
- 百度 AK 只允许 tx43/47/106 出口；本机走 `socks5h://127.0.0.1:10943`（xray 占用 10809，故用 10943）。

## 已知坑

- `vue-tsc -b` 曾生成 `vite.config.js` 覆盖 `.ts`；已改 build 为 `vue-tsc --noEmit`，不要再生成 js。
- Alembic autogenerate 曾把 JSONB default 渲染坏；`schedule` 默认已统一 `'{}'::jsonb`。
- 贝壳匿名只有第一页；翻页/最新/详情需登录态。
- 百度地理编码把「居里十舍」落到错误位置；百度只做兜底，必须交叉校验。
- 美团商家页返回键/控件树会卡；探针优先用 `--no-navigate`。
- 贝壳人机验证：CDP 每页新开/关闭标签页会触发；CDP 已改为复用标签页 + 6-12s 间隔，检测到验证即停并停任务。
- 贝壳 App API 翻页必须带 `feed_query_id`；不带时 offset 0/30/60 可能返回同一批。
- App API 单条件 offset 上限 2999、limit 上限 30；5 号线 total≈6689，无法一次抓全；API 全量扫描已自动跳过 suspect。
- App API 列表有随机性/重复，必须按 `house_code` 去重；当前每轮页内已去重。
- 高德已停用，本月用量预置 900/5000；POI/通勤不再消耗高德。
- 天地图每日约 10000 次；SZMC 零额度。
- 旧 AMAP 通勤样本按 1 天后重采为 SZMC；旧 POI 仍保留 AMAP 缓存。
- `enrich` 默认上限 100（单次约 500 次高德调用）、`rescore` 默认上限 2000（本地计算）；重复跑不会只处理前 200/500 条。
- API 只绑 LAN；已启用登录/RBAC，但仍**不要直接公网暴露**；公网前需 TLS/反向代理/限流。
- FastAPI SPA fallback 已对 `/api/*` 返回 JSON 404；未实现接口不会再返回 index.html。
- API 管理页、管理端全部页面走真实后端；用户端聊天已切真实 LLM Agent，未配置/失败时回退规则版；Agent 评测/成本页已接真实基线（2026-11-04）。
- `analysis` job 只做本地重评分，`sampling` job 只做单次采样；新增 `image_analysis` job 分析候选封面；详情多图仍不可用。
- `admin_settings` 已在通知、调度、额度、Agent 预算事件和监控推送运行时读取；设置页保存即生效。
- Agent 已接只读工具运行时（search/get/compare/commute/price），严格 JSON 计划 + 规则兜底；预算/PII/注入护栏；trace 落 `agent_tool_calls`；LLM 失败自动回退，不能把规则版回答标成模型输出。
- 封面管线只处理列表单图：本地缓存 + 64-bit dHash + 价格异常 + 中介话术；≥2 个非质量信号才可疑；视觉大模型未授权，`APP_IMAGE_VISION_ENABLED=false`。
- 口碑证据表 `reputation_mentions`：verified 计分、uncertain 只展示、rejected 排除；180 天半衰期；无证据显示“数据不足（中性分）”。
- 地图数据走 `/api/maps/communities`（GCJ-02→WGS-84）；天地图瓦片由后端 `/api/maps/tiles/...` 代理缓存，Key 不下发浏览器；无 Key 时前端回退坐标网格。
- P1 迁移 head `b2c3d4e5f6a7`（工具 trace / 封面 / 口碑 / 评测表）。
- ModelScope Key 已配置：provider 状态正常；业务 LLM 调用已回写 provider_usage。Key 来源 `/root/.credentials/modelscope.env`，项目 `.env` 为 600。
- V4.1F 是推理模型，响应含 `reasoning_content`；`max_tokens` 太小会把预算耗在思考上，当前解析 1200 / 回答 900。
- 模型页虽标 `SupportApiInference:false`，但 `/v1/models` 与真实 chat 均确认 `-1017` 可用；单模型约 500 次/天，注意别刷。
- Agent 仍是“LLM 解析 + 本地确定性查询 + LLM 回答”，没有让 LLM 自由调用工具；监控已接推送。
- SZMC `MinTimeJson` 无出发时间参数：4 个时段的结果相同，`static=true`；p90 只反映样本分布，不代表实时拥堵。不要把它写成“实时/高峰实测”。
- UI 证据截图用本地 mock API（`docs/evidence/p0-ui/`），因为 agent 无生产库权限；不是生产数据截图。

## 常用命令

```bash
cd /home/kkk/Project/rentradar
make db / migrate / seed / api / web / worker / scheduler / backup
cd backend
.venv/bin/python -m app.cli crawl --task-id 1 --pages 1 --sort newest --line li110460696 --transport api
.venv/bin/python -m app.cli crawl --task-id 1 --pages 1 --transport cdp   # CDP 兜底，需先过验证码
.venv/bin/python -m app.cli shards --line 5号线 --stations 20 --probe   # 生成/校验站点分片
.venv/bin/python -m app.cli apply-shards --task-id 1 --line 5号线   # 写入分片计划+10/180 调度
.venv/bin/python -m app.cli enrich --task-id 1 --limit 100
.venv/bin/python -m app.cli rescore --task-id 1 --limit 2000
.venv/bin/python -m app.cli digest --dry-run
.venv/bin/python -m app.cli probe --community-id 1 --no-navigate
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests
curl -s http://192.168.31.197:8010/api/admin/providers | python -m json.tool
curl -s -X POST http://192.168.31.197:8010/api/admin/providers/tianditu/test | python -m json.tool
```

## 验证基线（2026-11-04）

- 后端 119 passed；ruff 全绿；前端 `npm run build` 通过。

## 验证基线（2026-10-31）

- `pytest -q` → 57 passed；`ruff check app tests` 全绿；`npm run build` 通过。
- Alembic head：`f1a2b3c4d5e6`；`rentradar-api/worker/scheduler` 均 active。
- 登录/权限：匿名 `/api/admin/overview` → 401；viewer → 403；admin 登录后 200。
- 额度：AI 日上限设 0 时 Agent 自动回退规则版且 `provider_usage` 不增长；AMAP 上限设 900 时设置接口 400、无外部调用。
- 监控：测试监控扫描 2 天事件产生 711 条 pending，静默时未发送。
- 真实 LLM 会话：`model=deepseek-ai/DeepSeek-V4.1-Flash-1017`、tokens 745/513、fallback=false、约 4.5s。
- Provider 7 个：贝壳 API/CDP、天地图、深圳地铁官方 SZMC、高德、滴滴 MCP、魔搭 DeepSeek；高德/滴滴已停用，天地图地理编码/POI、SZMC 通勤为主通道。
- 用户端 `/` 真实对话、管理端 `/admin` 全部页面均已用无头 Chromium 验证。

## 剩余优先级（2026-10-31）

1. **P0**：Agent 工具运行时+护栏；5 号线完整覆盖（按站点/商圈拆分）。鉴权/RBAC、Provider 额度、设置运行时、监控推送已完成。
2. **P1**：图片/AI（详情图源需调研）；地铁 p50/p90+公交静态；开放数据参考租金/风险；地图 UI；Agent 评测/成本；口碑；外卖；价格历史/台账。
3. **P2**：多源（自如等）、多城市、滴滴/天地图产品化、分享/公网、账号/代理池、CI/CD/监控。

## 交接

完整交接见 `HANDOFF.md`。当前生产采集走贝壳 App API，快扫/慢扫均已恢复；CDP 因验证码暂停，仅作兜底。鉴权/额度/设置/监控运行时已接；下一步是 Agent 工具运行时、5 号线覆盖、图片 AI、地铁/开放数据与通勤 p50/p90。
