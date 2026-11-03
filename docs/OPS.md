# 运维手册（CI / 告警 / 备份 / 只读分享）

版本：2026-11-04 · 对应迁移 head `c3d4e5f6a7b8`

## 1. CI

`.github/workflows/ci.yml` 在 push/PR 上跑三个 job：

| Job | 内容 |
|---|---|
| `backend` | `ruff check app tests` + `pytest -q`（纯单元测试，不需要数据库） |
| `migrations` | Postgres 16 service → `alembic upgrade head` → `python -m app.cli check` → `alembic downgrade base` |
| `frontend` | `npm ci` + `npm run build`（`VITE_USE_MOCK=false`） |

CI 不访问外部模型/地图/飞书，不需要任何生产凭据。

## 2. 告警

scheduler 每 `alertIntervalMinutes`（默认 10 分钟）入队 `alert_check`，worker 采集快照后推送飞书：

| 告警 | 默认阈值 | 级别 |
|---|---|---|
| 数据库不可用 | `SELECT now()` 失败 | critical |
| 队列积压 | > `alertQueueBacklog`（100） | warning |
| 队列超时 | 最老排队 > `alertQueuedMinutes`（30） | critical |
| 作业失败 | 1 小时 ≥ 3 个 | warning |
| 源连续失败 | 某启用任务最近 3 次 run 全失败 | critical |
| Provider 熔断 | `circuit_open_until` 未到期 | warning |
| 磁盘 | `alertDiskPct`（85%；≥95 critical） | warning/critical |
| 备份失败 | `last_backup.json.status=failed` | critical |
| 备份过期 | 最新 dump > `alertBackupHours`（26h） | warning |

- 同一告警在 `alertCooldownMinutes`（30 分钟）内不重复推送；全部恢复时推一条“已恢复”。
- 设置页可改阈值并关闭 `alertPush`；手动检查：`python -m app.cli alert --dry-run`，或管理端「运维」页“立即检查告警”。
- 告警状态保存在 `app_settings.alert_state`，不单独建表。

## 3. 备份与恢复演练

```bash
# 生产机，operator 执行
bash deploy/scripts/backup.sh
# 恢复演练：解压到临时库 rentradar_restore_drill，跑计数后自动 drop
bash deploy/scripts/restore-drill.sh
```

- `backup.sh` 写 `$BACKUP_DIR/last_backup.json`（ok/failed + 时间 + 字节数），失败时保留 marker 供告警读取；dump 保留 7 天。
- `restore-drill.sh` 只操作 `rentradar_restore_drill`，不会覆盖生产库；成功输出 `listings/snapshots/users` 计数。
- 演练记录请写入 HANDOFF；当前仓库环境没有 Docker/psql，agent 未实际执行恢复。

## 4. 只读分享页

- 管理端「运维」页创建链接：返回一次完整 token（`rr_share_...`），数据库只存 SHA-256。
- 公开地址：`/share/<token>`；后端 `GET /api/public/dashboard/<token>`。
- 安全措施：撤销/过期校验、按 IP+token 60 次/分钟限流、`X-Robots-Tag: noindex, nofollow, noarchive`、`Cache-Control: no-store`、`Referrer-Policy: no-referrer`。
- 只返回聚合数据（总量、区域中位租金、价格带、5 号线分片摘要、回源链接），不返回标题/图片/地址/联系方式。
- **公网暴露前必须**：TLS 终止、反向代理、请求限流、`noindex` 响应头保留、日志脱敏。示例（Caddy）：

```caddyfile
rentradar.example.com {
  encode zstd gzip
  @public path /share/* /api/public/*
  header @public X-Robots-Tag "noindex, nofollow, noarchive"
  rate_limit @public { remote_ip } 60 events 1m
  reverse_proxy 127.0.0.1:8010
}
```

不要直接把 8010 映射到公网；管理端和用户端仍依赖登录 Cookie，当前 `APP_COOKIE_SECURE=false` 只适合 LAN HTTP。

## 5. 回滚

1. 停 scheduler/worker（operator）。
2. `alembic downgrade -1`（P2 迁移 `c3d4e5f6a7b8` 可逆）。
3. 恢复上一份 dump：`pg_restore` 到新库后切换 `APP_DATABASE_URL`，不要覆盖正在使用的库。
4. 重启三个 systemd 单元，`curl /health` 确认。
