# RentRadar

自用租房情报系统：贝壳 App 列表采集 → 评分/价格快照 → 一句话对话 Agent → 管理控制台。
深圳 5 号线为主要范围；地图用天地图 + 深圳地铁官方 SZMC，通知走飞书。

## 当前状态

- **P0**：5 号线站点分片覆盖、通勤 p50/p90、详情真实数据、看房清单/台账。
- **P1**：Agent 工具白名单 + 护栏 + 评测、封面 dHash/假房源信号、口碑证据链、真实地图。
- **P2/P3**：OpenCode Go DeepSeek V4.1 Flash、CI、运维告警、备份恢复演练、可撤销只读分享页、多城市/多来源、参考租金。
- **仍依赖人工/生产数据**：真实覆盖率、Top 候选通勤/价格点、外卖样本、住建局参考价数据、天地图 Key、视觉标签。见 `docs/P2-P4-COMPLETION.md`。

## 架构

```
浏览器 (Vue 3 SPA)
  ├─ /            用户端：对话 + 结果画布 + SSE
  ├─ /admin       管理端：总览/候选/通勤/质量/口碑/Provider/Agent/图片/运维/任务/日志/设置
  └─ /share/:tok  公开只读聚合看板（token 可撤销、noindex、限流）
FastAPI (8010, LAN only)
  ├─ /api/agent/*      SSE、sessions、monitors
  ├─ /api/admin/*      BFF、Provider、任务、运维、分享、来源/城市、参考租金
  ├─ /api/listings/*   详情、watchlist、inspection
  ├─ /api/maps/*       小区聚合 + 天地图瓦片代理
  └─ /api/public/*     只读聚合看板（无登录，token + 限流）
Postgres 16 · scheduler（入队） · worker（消费 jobs） · Alembic
Provider 运行时：额度/熔断/调用审计；贝壳 API、天地图、SZMC、OpenCode Go、ModelScope、飞书
```

## 快速开始（开发）

```bash
cp .env.example .env          # 填凭据；不要提交
make db migrate               # Postgres 容器 + alembic upgrade head
make seed                     # 演示数据
make api                      # 127.0.0.1:8010
make web                      # 127.0.0.1:5173（Vite，/api 代理到 8010）
```

后端：

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/ruff check app tests
.venv/bin/alembic heads
```

前端：

```bash
cd frontend
npm ci
npm run build        # FastAPI 托管 dist
npm run dev
```

## 常用命令

| 目的 | 命令 |
|---|---|
| 采集 | `python -m app.cli crawl --task-id 1 --pages 1 --transport api` |
| 5 号线分片 | `python -m app.cli shards --line 5号线 --probe` / `apply-shards --task-id 1 --line 5号线` |
| 重评分 | `python -m app.cli rescore --task-id 1 --limit 2000` |
| 告警 | `python -m app.cli alert --dry-run` |
| 手动房源导入 | `python -m app.cli import-listings --task-id <id> --file data/manual/feed.json` |
| 参考租金导入 | `python -m app.cli import-reference-rents --file data/reference-rents.json` |
| 手动记录外卖样本 | `python -m app.cli record-probe --community-id 1 --meal-period lunch --eta-low 28 --eta-high 35` |
| 备份 / 恢复演练 | `bash deploy/scripts/backup.sh` / `bash deploy/scripts/restore-drill.sh` |

## 文档

- `docs/P2-P4-COMPLETION.md`：计划书剩余工作与完成度（含未验证项）。
- `docs/OPS.md`：CI、告警、备份恢复、只读分享与公网暴露边界。
- `docs/API-SOURCES.md`：外部接口/数据源清单。
- `docs/TIANDITU-MAP.md`：天地图调研与瓦片代理。
- `HANDOFF.md` / `MEMORY.md`：运行交接与踩坑记录。
- `docs/PROJECT.md` / `docs/DEVELOPMENT.md`：v1.0 立项基线，仅历史参考。

## 安全边界

- 不要提交 `.env`、`.secrets/`、`data/`；日志/截图不要包含凭据或私人内容。
- 不要直接把 8010 暴露公网；分享页也必须先 TLS/反向代理/限流。
- 不做链家自动抓取；贝壳详情逆向不做；不自动把 `suspect` 改成 `gone`。
- Agent 只允许白名单工具；预算/PII/注入护栏在 `agent_service` / `guardrails.py`。
