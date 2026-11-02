# 租房雷达 RentRadar · 开发书

版本：v1.0
日期：2026-10-28
配套文档：`PROJECT.md`

## 1. 开发目标与约束

### 1.1 目标

- 两周内交付 P0：链家/贝壳列表采集、评分、快照、飞书、通勤、POI、看房清单、外卖探针试验；
- 架构按 P1/P2 设计，后续加详情登录、多城市、口碑、Web 台、公网看板不返工；
- 单机可跑，模块化单体，不引入微服务。

### 1.2 约束

- 单台家庭服务器（Ubuntu 24.04），Docker 可用；
- 低频采集，遵守 ToS/robots；
- LLM 只用免费额度（魔搭）或本地模型；
- 所有估算项必须标注「估算」，不伪造实时数据。

## 2. 开发环境

| 项 | 版本/说明 |
|---|---|
| Python | 3.12 |
| 包管理 | uv（推荐）或 pip + venv |
| Node | 20 LTS |
| 数据库 | PostgreSQL 16（Docker） |
| 浏览器 | Playwright Chromium |
| 容器 | Docker Compose v2 |
| 系统 | Ubuntu 24.04 |

### 2.1 依赖

后端：

```
fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic
pydantic pydantic-settings httpx[socks] selectolax
playwright apscheduler structlog python-dateutil
pillow imagehash cryptography argon2-cffi pyjwt
python-multipart tenacity
```

开发/测试：

```
pytest pytest-asyncio pytest-cov respx ruff mypy
```

前端：

```
vue typescript vite pinia vue-router
tailwindcss shadcn-vue echarts
@amap/amap-jsapi-loader axios
```

### 2.2 初始化

```bash
git clone <repo> rentradar && cd rentradar
cp .env.example .env
docker compose up -d postgres
uv sync
uv run alembic upgrade head
uv run playwright install chromium
cd frontend && npm ci && npm run build
```

## 3. 仓库结构

```
rentradar/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── cli.py                  # init/run/report/check
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings
│   │   │   ├── db.py               # engine/session
│   │   │   ├── security.py         # 密码/JWT/加密
│   │   │   ├── logging.py          # structlog
│   │   │   └── rate_limit.py       # 令牌桶
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── routes/             # auth/listings/tasks/accounts/...
│   │   ├── models/                 # SQLAlchemy
│   │   ├── schemas/                # Pydantic
│   │   ├── services/
│   │   │   ├── listing_service.py
│   │   │   ├── task_service.py
│   │   │   ├── job_service.py
│   │   │   ├── run_service.py
│   │   │   ├── notify_service.py
│   │   │   ├── score_service.py
│   │   │   ├── fake_service.py
│   │   │   └── report_service.py
│   │   ├── sources/
│   │   │   ├── base.py
│   │   │   ├── lianjia.py
│   │   │   ├── beike.py
│   │   │   └── registry.py
│   │   ├── geo/
│   │   │   ├── coords.py
│   │   │   ├── amap.py
│   │   │   ├── baidu.py
│   │   │   └── commute.py
│   │   ├── reputation/
│   │   │   ├── sources.py
│   │   │   ├── matcher.py
│   │   │   ├── extractor.py
│   │   │   └── aggregator.py
│   │   ├── delivery/
│   │   │   ├── poi.py
│   │   │   └── probe.py
│   │   └── workers/
│   │       ├── worker.py
│   │       └── scheduler.py
│   ├── alembic/
│   ├── tests/
│   │   ├── fixtures/               # HTML/JSON 快照
│   │   ├── unit/
│   │   ├── integration/
│   │   └── live/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── views/
│   │   ├── stores/
│   │   ├── router/
│   │   ├── composables/
│   │   └── lib/
│   └── package.json
├── deploy/
│   ├── docker-compose.yml
│   ├── nginx/
│   ├── systemd/
│   └── scripts/
├── docs/
│   ├── PROJECT.md
│   └── DEVELOPMENT.md
└── .env.example
```

## 4. 架构与进程模型

### 4.1 进程

| 进程 | 职责 | 副本 |
|---|---|---|
| api | FastAPI、WebSocket、静态前端 | 1（避免多 worker 状态不一致） |
| worker | 消费 jobs：抓取/富化/评分/通知 | 2-4 |
| scheduler | APScheduler，只入队 | 1 |
| postgres | 业务数据 + 队列 | 1 |
| nginx | TLS、反代、限流 | 1 |

### 4.2 队列

使用 Postgres `jobs` 表，不引入 Redis：

```sql
UPDATE jobs SET status='running', locked_by=$1, locked_at=now(), attempts=attempts+1
WHERE id = (
  SELECT id FROM jobs
  WHERE status='queued' AND run_after <= now()
  ORDER BY run_after
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
RETURNING *;
```

- 心跳：worker 每 30 秒更新 `locked_at`；
- 回收：`locked_at < now() - interval '10 minutes'` 的 running 任务重置为 queued；
- 幂等：每个 job 的业务键（如 `source_id + page`）唯一，重复执行不产生重复数据。

### 4.3 事件与实时

- 业务事件写 `events` 表；
- API 通过 Postgres `LISTEN/NOTIFY` 推送 WebSocket；
- 前端断线重连后按 `last_event_id` 拉增量。

## 5. 数据库设计

### 5.1 枚举

```sql
CREATE TYPE listing_status AS ENUM ('active','gone','suspect','relisted');
CREATE TYPE event_type AS ENUM ('new','price_drop','price_up','gone','relisted','suspect');
CREATE TYPE job_status AS ENUM ('queued','running','done','failed','canceled');
CREATE TYPE account_status AS ENUM ('active','cooldown','invalid','banned');
CREATE TYPE proxy_status AS ENUM ('active','cooldown','invalid');
```

### 5.2 用户与审计

```sql
CREATE TABLE users (
  id BIGSERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'admin',       -- admin/viewer
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  action TEXT NOT NULL,
  target TEXT,
  detail JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 5.3 城市/源/小区

```sql
CREATE TABLE cities (
  id BIGSERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,                -- sz/sh/bj
  name TEXT NOT NULL,
  domain_template TEXT NOT NULL,            -- https://{city}.lianjia.com
  center_lng DOUBLE PRECISION,
  center_lat DOUBLE PRECISION,
  enabled BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE sources (
  id BIGSERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,                -- lianjia/beike/ziroom/58/douban
  name TEXT NOT NULL,
  kind TEXT NOT NULL,                       -- html/api/js/login
  enabled BOOLEAN NOT NULL DEFAULT true,
  rate_limit JSONB NOT NULL DEFAULT '{"qps":0.3,"daily":2000}'
);

CREATE TABLE communities (
  id BIGSERIAL PRIMARY KEY,
  city_id BIGINT NOT NULL REFERENCES cities(id),
  name TEXT NOT NULL,
  district TEXT,
  lng DOUBLE PRECISION,
  lat DOUBLE PRECISION,
  coord_system TEXT NOT NULL DEFAULT 'GCJ02',
  adcode TEXT,
  geocode_confidence REAL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(city_id, name)
);

CREATE TABLE community_aliases (
  id BIGSERIAL PRIMARY KEY,
  community_id BIGINT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  UNIQUE(community_id, alias)
);
```

### 5.4 任务/队列/运行

```sql
CREATE TABLE tasks (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  city_id BIGINT NOT NULL REFERENCES cities(id),
  source_id BIGINT NOT NULL REFERENCES sources(id),
  filters JSONB NOT NULL DEFAULT '{}',
  schedule JSONB NOT NULL DEFAULT '{"fast_minutes":10,"slow_minutes":180}',
  account_strategy TEXT NOT NULL DEFAULT 'auto',   -- auto/fixed/rotate
  proxy_strategy TEXT NOT NULL DEFAULT 'direct',   -- direct/pool
  ai_config JSONB NOT NULL DEFAULT '{}',
  enabled BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE jobs (
  id BIGSERIAL PRIMARY KEY,
  task_id BIGINT REFERENCES tasks(id) ON DELETE CASCADE,
  type TEXT NOT NULL,                      -- crawl_list/crawl_detail/enrich/probe/digest
  payload JSONB NOT NULL DEFAULT '{}',
  status job_status NOT NULL DEFAULT 'queued',
  run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
  attempts INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  locked_by TEXT,
  locked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX jobs_claim_idx ON jobs(status, run_after);

CREATE TABLE runs (
  id BIGSERIAL PRIMARY KEY,
  task_id BIGINT REFERENCES tasks(id),
  job_id BIGINT REFERENCES jobs(id),
  status TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  stats JSONB NOT NULL DEFAULT '{}',
  error TEXT
);
```

### 5.5 房源/快照/图片/聚类

```sql
CREATE TABLE listings (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL REFERENCES sources(id),
  city_id BIGINT NOT NULL REFERENCES cities(id),
  community_id BIGINT REFERENCES communities(id),
  source_listing_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT,
  community_name TEXT,
  district TEXT,
  layout TEXT,
  area NUMERIC(6,2),
  orientation TEXT,
  floor TEXT,
  rent INTEGER,
  tags JSONB NOT NULL DEFAULT '[]',
  image_url TEXT,
  agent_type TEXT,                          -- agent/apartment/personal/unknown
  raw JSONB NOT NULL DEFAULT '{}',
  raw_hash TEXT,
  score INT,
  score_reasons JSONB NOT NULL DEFAULT '{}',
  status listing_status NOT NULL DEFAULT 'active',
  cluster_id BIGINT,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(source_id, source_listing_id)
);
CREATE INDEX listings_city_status_score_idx ON listings(city_id, status, score DESC);
CREATE INDEX listings_community_idx ON listings(community_id);

CREATE TABLE snapshots (
  id BIGSERIAL PRIMARY KEY,
  listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  rent INTEGER NOT NULL,
  seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  image_hash TEXT
);
CREATE INDEX snapshots_listing_time_idx ON snapshots(listing_id, seen_at);

CREATE TABLE images (
  id BIGSERIAL PRIMARY KEY,
  listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  phash TEXT,
  ai_labels JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clusters (
  id BIGSERIAL PRIMARY KEY,
  canonical_listing_id BIGINT NOT NULL REFERENCES listings(id),
  match_score REAL NOT NULL DEFAULT 0,
  reason JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
  id BIGSERIAL PRIMARY KEY,
  listing_id BIGINT REFERENCES listings(id) ON DELETE CASCADE,
  cluster_id BIGINT,
  type event_type NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  notified BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX events_notified_idx ON events(notified, created_at);
```

### 5.6 账号/代理

```sql
CREATE TABLE accounts (
  id BIGSERIAL PRIMARY KEY,
  source_id BIGINT NOT NULL REFERENCES sources(id),
  label TEXT NOT NULL,
  cookie_enc BYTEA NOT NULL,
  status account_status NOT NULL DEFAULT 'active',
  fail_count INT NOT NULL DEFAULT 0,
  last_used_at TIMESTAMPTZ,
  cooldown_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE proxies (
  id BIGSERIAL PRIMARY KEY,
  url_enc BYTEA NOT NULL,
  region TEXT,
  provider TEXT,
  status proxy_status NOT NULL DEFAULT 'active',
  fail_count INT NOT NULL DEFAULT 0,
  cooldown_until TIMESTAMPTZ,
  cost_per_gb NUMERIC(8,2) DEFAULT 0,
  last_used_at TIMESTAMPTZ
);
```

### 5.7 通勤/站点/外卖/口碑

```sql
CREATE TABLE commute_samples (
  id BIGSERIAL PRIMARY KEY,
  community_id BIGINT NOT NULL REFERENCES communities(id),
  listing_id BIGINT REFERENCES listings(id),
  origin_hash TEXT NOT NULL,
  mode TEXT NOT NULL,                       -- transit/driving/bicycling/walking
  depart_bucket TEXT NOT NULL,              -- weekday_0830
  duration_s INT NOT NULL,
  distance_m INT,
  transfers INT DEFAULT 0,
  provider TEXT NOT NULL,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stations (
  id BIGSERIAL PRIMARY KEY,
  city_id BIGINT NOT NULL REFERENCES cities(id),
  name TEXT NOT NULL,
  lines TEXT[] DEFAULT '{}',
  lng DOUBLE PRECISION,
  lat DOUBLE PRECISION,
  daily_ridership INT,
  peak_share REAL,
  headway_s INT,
  is_transfer BOOLEAN DEFAULT false,
  crowd_index REAL,
  restricted_windows JSONB DEFAULT '[]',
  UNIQUE(city_id, name)
);

CREATE TABLE station_notes (
  id BIGSERIAL PRIMARY KEY,
  station_id BIGINT NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
  source TEXT,
  url TEXT,
  published_at TIMESTAMPTZ,
  text TEXT,
  severity INT DEFAULT 1
);

CREATE TABLE delivery_probes (
  id BIGSERIAL PRIMARY KEY,
  community_id BIGINT NOT NULL REFERENCES communities(id),
  platform TEXT NOT NULL,                   -- meituan/eleme/taobao/jd
  probe_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  meal_period TEXT,                         -- lunch/dinner/late_night
  address_label TEXT,
  eta_min_low INT,
  eta_min_high INT,
  fee NUMERIC(6,2),
  merchant_count INT,
  raw_text TEXT,
  screenshot_paths JSONB DEFAULT '[]',
  confidence REAL,
  device_id TEXT
);

CREATE TABLE reputation_mentions (
  id BIGSERIAL PRIMARY KEY,
  community_id BIGINT NOT NULL REFERENCES communities(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  author_hash TEXT,
  published_at TIMESTAMPTZ,
  text TEXT,
  issue_type TEXT NOT NULL,
  severity INT,
  building TEXT,
  floor TEXT,
  quote TEXT,
  confidence REAL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(source, url)
);
CREATE INDEX reputation_community_idx ON reputation_mentions(community_id, published_at);
```

### 5.8 台账/黑名单/AI/设置

```sql
CREATE TABLE watchlist (
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  state TEXT NOT NULL DEFAULT 'new',        -- new/seen/contacted/viewed/rejected
  note TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE blacklist (
  id BIGSERIAL PRIMARY KEY,
  kind TEXT NOT NULL,                       -- community/keyword/agent/image_hash
  value TEXT NOT NULL,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(kind, value)
);

CREATE TABLE ai_jobs (
  id BIGSERIAL PRIMARY KEY,
  listing_id BIGINT REFERENCES listings(id) ON DELETE CASCADE,
  type TEXT NOT NULL,                       -- photo/text/reputation
  status job_status NOT NULL DEFAULT 'queued',
  result JSONB,
  cost NUMERIC(8,4) DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## 6. 后端模块

### 6.1 分层

```
api/routes → services → models/db
                ↓
        sources / geo / reputation / delivery / notify
```

规则：

- routes 只做参数校验与响应，不写业务；
- services 负责事务边界；
- sources 只负责取数与解析，返回 `ListingDraft`；
- 外部调用统一走 `core/http.py`（超时、重试、代理、限流、日志）。

### 6.2 核心服务

| 服务 | 职责 |
|---|---|
| `listing_service` | 房源 CRUD、过滤、状态、聚类 |
| `task_service` | 任务 CRUD、启停、生成 job |
| `job_service` | 入队、认领、心跳、回收 |
| `run_service` | 运行记录、统计、错误 |
| `score_service` | 硬过滤、打分、理由 |
| `fake_service` | 图片 hash、价格分位、话术 |
| `notify_service` | 飞书、去重、静默、日报 |
| `report_service` | 日报/周报/公网快照 |

### 6.3 配置

`.env`：

```
APP_ENV=prod
APP_DATABASE_URL=postgresql+asyncpg://rentradar:pass@postgres:5432/rentradar
APP_SECRET_KEY=...
APP_FERNET_KEY=...
APP_BASE_URL=https://rent.example.com
FEISHU_WEBHOOK=...
AMAP_WEB_KEY=...
AMAP_JS_KEY=...
AMAP_JS_SECURITY_CODE=...
BAIDU_AK=...
AI_BASE_URL=...
AI_API_KEY=...
AI_MODEL=...
PROBE_DEVICE_ID=iphone11
```

## 7. 采集器规范

### 7.1 适配器接口

```python
class SourceAdapter(Protocol):
    code: str
    requires_login: bool

    async def fetch_list(self, ctx: FetchContext) -> str: ...
    def parse_list(self, html: str, ctx: ParseContext) -> list[ListingDraft]: ...
    async def fetch_detail(self, ctx: DetailContext) -> str: ...
    def parse_detail(self, html: str, draft: ListingDraft) -> ListingDraft: ...
```

### 7.2 链家列表（P0）

- URL：`https://{city}.lianjia.com/zufang/rco11/`（最新上架），翻页 `/rco11/pg{n}/`；
- 解析：`div.content__list--item`，取 `data-house_code`、标题、小区、户型、面积、朝向、楼层、价格、标签、图片、链接；
- 只取前 1-2 页（快循环）；慢循环取筛选后的 5-10 页；
- 详情页 302 登录，P0 不抓；
- 页面校验：列表节点数 > 0、标题含「租房」、无验证码关键词。

### 7.3 贝壳（P0/P1）

- 与链家同源，域名/结构**待实测**；
- 先做列表，详情 P1；
- 与链家跨源聚类，避免重复通知。

### 7.4 详情与账号（P1）

- Playwright persistent context + cookie 注入；
- 登录失效检测：302 `clogin`、页面含「请登录」；
- 账号选择：`auto/fixed/rotate`，单账号 QPS 限制；
- 失败：`fail_count++`，达到阈值冷却 30-120 分钟，连续 3 次熔断并告警；
- Cookie 加密存储，日志脱敏。

### 7.5 反爬与限速

| 源 | QPS | 说明 |
|---|---|---|
| 链家/贝壳列表 | 0.3 | 1 请求 / 3-4s，带 jitter |
| 链家/贝壳详情 | 0.2 | 登录态，低频 |
| 58/安居客 | 0.2 | P2，代理优先 |
| 豆瓣/论坛 | 0.2 | P1，低频 |

- 统一 UA、Accept-Language、Referer；
- 429/403/验证码：停止该源本轮，记失败，不清空现有数据；
- 不重试验证码页，避免越试越封。

### 7.6 解析测试

每个源必须有 HTML fixture：

```
tests/fixtures/lianjia_list_sz.html
tests/fixtures/lianjia_detail.html
```

测试断言：条数、关键字段、价格解析、分页链接、异常页识别。

## 8. 调度与任务

### 8.1 两档轮询

| 任务 | 频率 | 范围 |
|---|---|---|
| `crawl_list_fast` | 10 分钟 | 最新上架前 1-2 页 |
| `crawl_list_slow` | 2-6 小时 | 筛选条件全量 |
| `crawl_detail` | 按需 | 新/变化房源 |
| `enrich_geo` | 每日 | 新小区 |
| `enrich_reputation` | 每日/按需 | Top 候选 |
| `probe_delivery` | 每日 2-3 次 | Top 3-5 小区 |
| `send_digest` | 每日 09:00 | 全部 |

### 8.2 冷启动

首次运行：

- 抓到的房源全部入库，`events` 不生成 `new`，或 `notified=true`；
- 建立价格基线；
- 从第二次运行开始才推送。

### 8.3 失败保护

- 连续 3 次失败 → 源冷却 2 小时；
- 每天最多一次失败通知；
- 成功运行才允许标记 `gone`；
- 连续 2 次成功运行未出现才 `gone`。

## 9. 评分算法

### 9.1 伪代码

```python
def score_listing(listing, ctx) -> ScoreResult | None:
    if not passes_hard_filters(listing, ctx.filters):
        return None

    reasons = {}
    total = 0.0

    total += 35 * price_score(listing, ctx.market)
    total += 25 * commute_score(ctx.commute)
    total += 15 * condition_score(listing)
    total += 10 * convenience_score(ctx.poi)
    total += 10 * reputation_score(ctx.reputation)
    total += 5 * freshness_score(listing)

    penalty = risk_penalty(listing, ctx)
    total = clamp(round(total - penalty), 0, 100)
    return ScoreResult(total, reasons)
```

### 9.2 子分

**性价比**

```
median = 同小区同户型 30 天中位价
if median is None: score = 0.5
delta = (median - rent) / median
score = clamp(0.5 + delta / 0.4, 0, 1)   # 低 20% 满分，高 20% 零分
```

**通勤**

```
p50 分钟：<=30 → 1.0；30-60 → 线性；>60 → 0
p90 稳定性：p90 - p50 > 20 分钟，扣 10%
```

**居住条件**

电梯 30%、朝向 20%、楼层 20%、面积 15%、装修 15%。

**生活便利**

餐饮密度 40%、品类多样性 20%、夜宵 15%、日常采购 15%、实测外卖 10%。

**口碑**

```
weighted = sum(severity * 0.5 ** (age_days / 270) * source_weight)
confidence = f(mentions, sources, recency)
if confidence < 0.3: score = 0.5 (不扣分)
else: score = clamp(1 - weighted / threshold, 0, 1)
```

**新鲜度**

6h 内 1.0，24h 内 0.6，72h 内 0.3，否则 0.1。

**风险扣分**

- 假房源信号：每个 -10，最多 -30；
- 距主干道 <100m / 铁路 <300m / 工地 <500m：-5 到 -15；
- 骑手不能进小区：-3；
- 严重口碑硬伤（高置信）：-5 到 -15。

### 9.3 解释

`score_reasons` 必须包含每个维度的可读理由；估算项带 `"estimated": true`。

## 10. 口碑模块

### 10.1 流程

```
候选小区 → 生成查询词（名称 + 别名 + 问题词）
→ 平台适配器取结果 → 相关性过滤（必须提到小区 + 问题）
→ 去重（URL/文本 hash）→ LLM 抽取（严格 JSON）
→ 聚合（时间衰减/来源多样性/置信度）→ 证据入库
```

### 10.2 问题分类

`soundproofing / leak / water / power / network / elevator / property / noise / damp / pest / parking / safety / other`

### 10.3 抽取 schema

```json
{
  "community": "居里十舍",
  "issue_type": "soundproofing",
  "severity": 4,
  "building": "3栋",
  "floor": "临街",
  "time_hint": "2026-03",
  "quote": "晚上车流声很大，墙体薄，隔壁说话能听见",
  "confidence": 0.8
}
```

### 10.4 实体对齐

- 主键：链家/贝壳小区名 + 区 + 坐标；
- 别名表：一期/二期/别名/简称；
- 匹配条件：城市 + 区 + 名称相似度 + 800m 内 POI；
- 不确定标 `uncertain`，不参与评分，只展示原文。

### 10.5 数据源

P1：豆瓣租房小组、本地论坛、12345/领导留言板；
P2：小红书、微博、知乎、贴吧。

### 10.6 合规

- 只展示原文摘录 + 链接 + 「未经核实」；
- 不公开用户名/头像/联系方式；
- 不输出「该小区漏水」这类断言；
- 公网看板默认不展示口碑原文。

## 11. 地图/通勤/拥挤度

### 11.1 坐标

- 高德/腾讯：GCJ-02；百度：BD-09；GPS：WGS-84；
- 入库带 `coord_system`，统一转 GCJ-02；
- 高德经纬度顺序 `lng,lat`，百度 `lat,lng`。

### 11.2 接口

| 能力 | 高德 | 百度 |
|---|---|---|
| 地理编码 | `/v3/geocode/geo` | `/geocoding/v3/` |
| 逆地理 | `/v3/geocode/regeo` | `/reverse_geocoding/v3/` |
| 公交 | `/v3/direction/transit/integrated` | `/directionlite/v1/transit` |
| 驾车 | `/v3/direction/driving` | `/directionlite/v1/driving` |
| 骑行 | `/v4/direction/bicycling` | `/directionlite/v1/riding` |
| 步行 | `/v3/direction/walking` | `/directionlite/v1/walking` |
| POI | `/v3/place/around` | `/place/v2/search` |
| 路况 | `/v3/traffic/status/*` | `/traffic/v1/*` |

### 11.3 缓存

| 数据 | TTL |
|---|---|
| 地理编码 | 永久 + 人工校正 |
| 通勤 | 7 天，按 `origin_hash + mode + depart_bucket` |
| POI | 30 天 |
| 口碑 | 30 天 |

### 11.4 通勤采样

- 只对候选房源；
- 工作日 7:30/8:00/8:30/9:00 各一次；
- 连续 2 周，算 p50/p90；
- 记录天气/是否高峰。

### 11.5 拥挤度估算

```
crowd_index = 0.4 * ridership_norm
            + 0.2 * peak_share
            + 0.15 * transfer_penalty
            + 0.15 * job_density
            + 0.1 * (1 / headway_norm)
```

- 站级客流来自官方发布；
- 限流公告作为强信号；
- 只做相对排序，明确标「估算」；
- 不做实时人数。

## 12. 外卖探针

### 12.1 设备与能力

- iPhone 11 Pro + `ipctl` / `iph-daemon`；
- 截图、点击、拖动、输入、启动 App、语义控件树；
- 模拟定位（待实测）或预存地址优先。

### 12.2 App

| App | Bundle ID | 用途 |
|---|---|---|
| 美团 | `com.meituan.imeituan` | 餐饮外卖 ETA/运费 |
| 饿了么 | 待确认 | 交叉验证 |
| 淘宝 | `com.taobao.taobao4iphone` | 闪购/即时零售 |
| 京东 | `com.360buy.jdmobile` | 秒送 |

### 12.3 流程

```
设置定位/切换地址 → 启动 App → 等待稳定 → 关弹窗
→ 打开外卖/闪购首页 → 等待列表 → 截图 3 张
→ 控件树提取 ETA/运费/商家数 → 入库 → 退出 → 恢复定位
```

- 不进入提交订单页，避免误下单；
- 地址优先：每个目标小区预存一个收货地址；
- 低频：每小区每天 2-3 次；
- 失败重试 1 次，仍失败告警；
- 截图脱敏存储，公网不发布。

### 12.4 解析

- 优先 iOS 控件树文本（`预计 30-40 分钟`、`配送费 ¥3`）；
- 缺失再用 Qwen-VL OCR；
- ETA 区间取中值；
- 记录样本数与置信度。

## 13. 通知

### 13.1 飞书

- P0：群机器人 webhook，文本/富文本；
- P1：应用 bot，支持图片卡片（image_key）；
- 消息结构：标题、价格、小区、户型/面积/楼层/朝向、评分与 Top 3 理由、通勤、外卖、链接。

### 13.2 去重与节流

- `events.notified` 标记；
- 簇级去重：同簇只推一次；
- 每轮最多 5 条；
- 23:00-08:00 静默（高优先级可配置例外）；
- 首次基线不推送。

### 13.3 日报 09:00

- 今日新增 Top 10；
- 降价 Top 5；
- 市场统计：新增数、中位价、下架数、源健康度。

## 14. API 规范

### 14.1 认证

- `POST /api/auth/login` → access + refresh（httpOnly cookie）；
- `POST /api/auth/refresh`；
- `POST /api/auth/logout`；
- `GET /api/auth/me`。

### 14.2 业务

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/dashboard` | 汇总指标 |
| GET | `/api/listings` | 筛选/分页/排序 |
| GET | `/api/listings/{id}` | 详情 + 快照 + 证据 |
| PATCH | `/api/listings/{id}/state` | 台账状态 |
| POST | `/api/listings/{id}/blacklist` | 拉黑 |
| GET | `/api/communities/{id}` | 小区画像 |
| GET | `/api/tasks` | 任务列表 |
| POST | `/api/tasks` | 创建 |
| PATCH | `/api/tasks/{id}` | 更新 |
| POST | `/api/tasks/{id}/run` | 立即运行 |
| GET | `/api/runs` | 运行记录 |
| GET | `/api/accounts` | 账号 |
| POST | `/api/accounts` | 导入 Cookie |
| POST | `/api/accounts/{id}/check` | 健康检查 |
| GET | `/api/proxies` | 代理 |
| GET | `/api/logs` | 日志 |
| GET | `/api/settings` | 设置 |
| PUT | `/api/settings` | 更新 |
| GET | `/share/{token}` | 公网只读 |
| WS | `/ws` | 事件推送 |

### 14.3 约定

- 分页：`page/page_size`，返回 `items/total`；
- 错误：`{code, message, detail}`；
- 所有时间 UTC 存储，前端按本地时区展示；
- OpenAPI 自动生成 `/docs`，生产关闭或加鉴权。

## 15. 前端设计

### 15.1 路由

```
/login
/                 Dashboard
/listings         房源列表
/listings/:id     房源详情
/map              地图
/tasks            任务
/accounts         账号
/proxies          代理
/logs             日志
/settings         设置
/share/:token     公网只读
```

### 15.2 组件

- `ListingCard`、`ListingTable`、`ScoreBreakdown`、`PriceChart`；
- `CommutePanel`、`ReputationPanel`、`DeliveryPanel`、`InspectionChecklist`；
- `TaskForm`、`AccountImport`、`SourceHealth`；
- `MapView`（高德 JS + marker cluster）。

### 15.3 状态

- Pinia：auth、listings、tasks、settings；
- API client 统一处理 401/刷新/错误提示；
- WebSocket 断线重连 + 增量拉取。

### 15.4 构建

```bash
cd frontend
npm ci
npm run build   # 输出 dist/
```

FastAPI 托管 `dist/`，Nginx 反代 `/api`、`/ws`。

## 16. 安全

- 密码：Argon2id；
- JWT：access 15 分钟，refresh 7 天，httpOnly + Secure + SameSite；
- CSRF：cookie 流程加 token；
- RBAC：admin/viewer；
- 登录限流：IP + 账号；
- 敏感字段：Cookie/代理用 Fernet 加密，密钥在 env；
- 日志：手机号/地址/Cookie 脱敏；
- 公网：TLS、HSTS、fail2ban、限流、noindex；
- 公网看板：token 可撤销/过期，只展示脱敏字段；
- 审计：账号导入/导出、设置变更、任务启停；
- 备份：加密后异地存储。

## 17. 部署与运维

### 17.1 Compose

```yaml
services:
  postgres:
    image: postgres:16
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck: ...
  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    depends_on: [postgres]
  worker:
    build: ./backend
    command: python -m app.workers.worker
  scheduler:
    build: ./backend
    command: python -m app.workers.scheduler
  nginx:
    image: nginx:alpine
    ports: ["443:443", "80:80"]
    volumes: [./deploy/nginx:/etc/nginx/conf.d, certs:/etc/nginx/certs]
  backup:
    image: postgres:16
    command: /scripts/backup.sh
```

### 17.2 运维命令

```bash
docker compose up -d
docker compose exec api alembic upgrade head
docker compose logs -f worker
docker compose restart worker
```

### 17.3 备份

```bash
pg_dump -Fc rentradar > /backup/rentradar_$(date +%F).dump
rsync -az /backup/ fn2:/volume1/backup/rentradar/
```

保留 7 天日备 + 4 周周备；恢复演练每季度一次。

### 17.4 监控

- `/health`（DB/队列/磁盘）；
- Uptime Kuma 探活；
- 队列积压 > 100 告警；
- 源连续失败告警；
- 磁盘 < 15% 告警；
- 飞书告警群。

### 17.5 故障排查

| 现象 | 排查 |
|---|---|
| 采集 0 条 | 验证码/改版/登录失效；看 `runs.error` 与页面快照 |
| 队列不动 | worker 是否存活、`locked_at` 是否卡死 |
| 飞书 403 | webhook 失效/签名/频率 |
| 高德配额 | 控制台用量、缓存命中率 |
| 误标下架 | 检查是否失败运行也执行了 gone 逻辑 |
| iPhone 探针失败 | 电量/锁屏/App 登录/网络/控件树变化 |

## 18. 测试与 CI

### 18.1 测试

- 单元：解析 fixture、评分、坐标转换、实体匹配、假房源；
- 集成：API、任务认领、通知 mock、DB 事务；
- Live smoke：链家 1 页、高德 1 次、飞书 1 条（可选，手动触发）。

目标覆盖率：核心 services/parsers ≥ 70%。

### 18.2 CI

```
ruff check
ruff format --check
pytest -q
cd frontend && npm ci && npm run build
docker compose build
```

合并前必须全绿；live smoke 不进 CI。

## 19. 开发规范

- Python：ruff + 类型注解；异步优先；
- 命名：模块 snake_case，类 PascalCase；
- 错误：业务异常用自定义 `AppError`，不吞异常；
- 日志：structlog JSON，带 `task_id/job_id/source`；
- 配置：全部走 env/pydantic-settings，不硬编码；
- 提交：`feat/fix/chore/docs` + 简短说明；
- 分支：`main` + feature 分支，PR 合并；
- 不提交密钥、Cookie、截图中的个人信息。

## 20. 两周开发计划

| 天 | 任务 | 交付 |
|---|---|---|
| D1 | 仓库、Compose、Postgres、Alembic、配置、日志 | 可启动骨架 |
| D2 | 链家列表适配器 + fixture + 解析测试 | 能抓 30 条并入库 |
| D3 | jobs/scheduler/worker + runs | 定时任务可跑 |
| D4 | 硬过滤 + 评分 + 房源 API | 分数与理由可查 |
| D5 | 飞书即时 + 冷启动基线 + 去重 | 新房源推送 |
| D6 | 快照/降价/下架 + 失败保护 | 事件完整 |
| D7 | 贝壳适配器（待实测） | 双源 |
| D8 | 高德地理编码 + 通勤采样 + 缓存 | 通勤 p50/p90 |
| D9 | POI 生活便利 + 噪音源 + 评分接入 | 便利分 |
| D10 | 看房清单 + 台账 | 可回填 |
| D11 | iPhone 外卖探针（美团 + 1 小区） | 样本入库 |
| D12 | 端到端跑 24 小时 + 修 bug | 稳定运行 |
| D13 | 日报/周报 + 文档 + 备份脚本 | 可运维 |
| D14 | 验收 + 复盘 + P1 排期 | 交付 |

P1/P2 按项目书第 10 节推进。

## 21. 验收清单（P0）

- [ ] `docker compose up -d` 一键起
- [ ] 迁移成功，表结构完整
- [ ] 链家列表解析成功率 > 95%
- [ ] 评分理由可读，无空理由
- [ ] 飞书即时/日报正常，静默生效
- [ ] 首次运行不推送
- [ ] 失败运行不标下架
- [ ] 通勤 p50/p90 可查
- [ ] POI 便利分可查
- [ ] 看房清单可保存/导出
- [ ] 外卖探针 ≥ 20 条有效样本
- [ ] 备份脚本可恢复
- [ ] 日志可定位每次 run 的失败原因

## 22. 附录

### 22.1 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| APP_DATABASE_URL | 是 | Postgres DSN |
| APP_SECRET_KEY | 是 | JWT 签名 |
| APP_FERNET_KEY | 是 | Cookie/代理加密 |
| FEISHU_WEBHOOK | P0 | 飞书群机器人 |
| AMAP_WEB_KEY | P0 | 服务端 |
| AMAP_JS_KEY | P1 | 前端 |
| AMAP_JS_SECURITY_CODE | P1 | 前端 |
| BAIDU_AK | P1 | 兜底 |
| AI_BASE_URL / AI_API_KEY / AI_MODEL | P1 | 口碑/图片 |
| PROBE_DEVICE_ID | P0 | iPhone 标识 |

### 22.2 术语

- **快循环**：10 分钟抓最新上架；
- **慢循环**：2-6 小时全量；
- **冷启动基线**：首次只入库不推送；
- **簇**：跨源/重复房源的聚合；
- **置信度**：口碑/探针样本的可信程度；
- **p50/p90**：通勤耗时的中位数与 90 分位。
