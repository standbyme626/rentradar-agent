"""Operational alerts (P2/W8).

The scheduler enqueues an ``alert_check`` job every ``alertIntervalMinutes``.
The worker collects a cheap snapshot, turns it into alert codes, de-duplicates
against the last sent batch and pushes a short Feishu message.  Collection and
evaluation are separated so the thresholds are unit-testable without a DB.
"""

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import AppSetting, Job, JobStatus, ProviderHealth, Run, Task
from app.services.notify_service import send_text
from app.services.settings_service import get_admin_settings

log = get_logger("alert")
ALERT_STATE_KEY = "alert_state"
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _age_minutes(value: datetime | None, now: datetime | None = None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return max(0.0, ((now or datetime.now(UTC)) - value).total_seconds() / 60)


def _backup_snapshot(path: Path) -> dict[str, Any]:
    marker = path / "last_backup.json"
    dumps = sorted(path.glob("rentradar_*.dump"), key=lambda item: item.stat().st_mtime)
    latest_age_hours = None
    if dumps:
        latest_age_hours = round(
            (datetime.now().timestamp() - dumps[-1].stat().st_mtime) / 3600, 1
        )
    marker_data: dict[str, Any] = {}
    if marker.is_file():
        try:
            marker_data = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            marker_data = {"status": "unreadable"}
    return {
        "configured": path.is_dir(),
        "dir": str(path),
        "latest_age_hours": latest_age_hours,
        "marker": marker_data,
    }


def evaluate_alerts(snapshot: dict[str, Any], admin_settings: dict) -> list[dict]:
    """Turn a status snapshot into de-duplicable alert records."""
    alerts: list[dict] = []

    def add(code: str, severity: str, message: str):
        alerts.append({"code": code, "severity": severity, "message": message})

    if snapshot.get("db") != "ok":
        add("db_unavailable", "critical", "数据库连接异常，API/worker 无法正常写入。")

    queued = int(snapshot.get("queued_jobs") or 0)
    backlog = int(admin_settings.get("alertQueueBacklog") or 100)
    if queued > backlog:
        add(
            "queue_backlog",
            "warning",
            f"队列积压 {queued} 个作业，超过阈值 {backlog}。",
        )
    oldest = snapshot.get("oldest_queued_minutes")
    queued_minutes = int(admin_settings.get("alertQueuedMinutes") or 30)
    if oldest is not None and oldest > queued_minutes:
        add(
            "queue_stale",
            "critical",
            f"最老排队作业已等待 {oldest:.0f} 分钟，worker 可能停摆。",
        )

    failed = int(snapshot.get("failed_jobs_1h") or 0)
    if failed >= 3:
        add("job_failures", "warning", f"最近 1 小时有 {failed} 个失败作业。")

    for task in snapshot.get("failing_tasks") or []:
        add(
            f"source_failed:{task.get('task_id')}",
            "critical",
            f"采集任务「{task.get('name') or task.get('task_id')}」连续 3 次失败："
            f"{task.get('last_error') or '无错误详情'}",
        )

    for item in snapshot.get("providers") or []:
        if item.get("circuit_open_until"):
            add(
                f"provider_circuit:{item.get('code')}",
                "warning",
                f"Provider {item.get('code')} 熔断中（{item.get('last_error') or '连续失败'}）。",
            )

    disk = snapshot.get("disk") or {}
    used_pct = disk.get("used_pct")
    disk_pct = int(admin_settings.get("alertDiskPct") or 85)
    if used_pct is not None and float(used_pct) >= disk_pct:
        add(
            "disk_high",
            "critical" if float(used_pct) >= 95 else "warning",
            f"磁盘 {disk.get('path') or ''} 使用率 {float(used_pct):.0f}%，"
            f"阈值 {disk_pct}%。",
        )

    backup = snapshot.get("backup") or {}
    marker = backup.get("marker") or {}
    if marker.get("status") == "failed":
        add(
            "backup_failed",
            "critical",
            f"最近一次备份失败：{str(marker.get('error') or '未知错误')[:120]}",
        )
    backup_hours = int(admin_settings.get("alertBackupHours") or 26)
    latest_age = backup.get("latest_age_hours")
    if backup.get("configured") and latest_age is not None and latest_age > backup_hours:
        add(
            "backup_stale",
            "warning",
            f"最新备份已 {latest_age:.0f} 小时未更新，阈值 {backup_hours} 小时。",
        )
    return sorted(alerts, key=lambda item: SEVERITY_ORDER.get(item["severity"], 9))


def format_alert_text(alerts: list[dict], *, recovered: list[str] | None = None) -> str:
    lines = ["RentRadar 运维告警"]
    for item in alerts:
        icon = "🔴" if item["severity"] == "critical" else "🟠"
        lines.append(f"{icon} [{item['code']}] {item['message']}")
    if recovered:
        lines.append(f"✅ 已恢复：{', '.join(recovered)}")
    return "\n".join(lines)


async def collect_snapshot(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    try:
        await db.execute(select(func.now()))
        db_state = "ok"
    except Exception as exc:  # pragma: no cover - operational guard
        log.error("alert_snapshot_db_failed", error=str(exc)[:200])
        db_state = "error"

    queued = int(
        await db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.queued)
        )
        or 0
    )
    running = int(
        await db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.running)
        )
        or 0
    )
    oldest_queued = await db.scalar(
        select(func.min(Job.created_at)).where(Job.status == JobStatus.queued)
    )
    failed_1h = int(
        await db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.status == JobStatus.failed,
                Job.created_at >= now - timedelta(hours=1),
            )
        )
        or 0
    )

    failing_tasks: list[dict] = []
    tasks = (
        (await db.execute(select(Task).where(Task.enabled.is_(True)))).scalars().all()
    )
    for task in tasks:
        runs = (
            await db.execute(
                select(Run.status, Run.error)
                .where(Run.task_id == task.id)
                .order_by(Run.started_at.desc())
                .limit(3)
            )
        ).all()
        if len(runs) == 3 and all(row[0] == "failed" for row in runs):
            failing_tasks.append(
                {
                    "task_id": task.id,
                    "name": task.name,
                    "last_error": (runs[0][1] or "")[:200],
                }
            )

    providers = [
        {
            "code": row.provider,
            "status": row.status,
            "consecutive_failures": int(row.consecutive_failures or 0),
            "circuit_open_until": (
                row.circuit_open_until.isoformat() if row.circuit_open_until else None
            ),
            "last_error": row.last_error,
        }
        for row in (
            await db.execute(select(ProviderHealth).order_by(ProviderHealth.provider))
        )
        .scalars()
        .all()
    ]

    disk_path = Path(settings.alert_disk_path or ".")
    disk: dict[str, Any] | None = None
    try:
        usage = shutil.disk_usage(disk_path)
        disk = {
            "path": str(disk_path.resolve()),
            "used_pct": round(usage.used / max(1, usage.total) * 100, 1),
            "free_gb": round(usage.free / 1024**3, 1),
        }
    except OSError:
        disk = None

    return {
        "generated_at": now.isoformat(),
        "db": db_state,
        "queued_jobs": queued,
        "running_jobs": running,
        "oldest_queued_minutes": (
            round(_age_minutes(oldest_queued, now) or 0, 1)
            if oldest_queued is not None
            else None
        ),
        "failed_jobs_1h": failed_1h,
        "failing_tasks": failing_tasks,
        "providers": providers,
        "disk": disk,
        "backup": _backup_snapshot(Path(settings.backup_dir)),
    }


async def safe_snapshot(db: AsyncSession) -> dict[str, Any]:
    try:
        return await collect_snapshot(db)
    except Exception as exc:  # pragma: no cover - operational guard
        log.error("alert_snapshot_failed", error=str(exc)[:200])
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "db": "error",
            "queued_jobs": 0,
            "running_jobs": 0,
            "oldest_queued_minutes": None,
            "failed_jobs_1h": 0,
            "failing_tasks": [],
            "providers": [],
            "disk": None,
            "backup": {
                "configured": False,
                "dir": str(settings.backup_dir),
                "latest_age_hours": None,
                "marker": {},
            },
            "error": f"{type(exc).__name__}: {exc}"[:300],
        }


async def _load_state(db: AsyncSession) -> dict:
    setting = await db.get(AppSetting, ALERT_STATE_KEY)
    return dict(setting.value) if setting and setting.value else {}


async def get_state(db: AsyncSession) -> dict:
    return await _load_state(db)


async def _save_state(db: AsyncSession, value: dict) -> None:
    setting = await db.get(AppSetting, ALERT_STATE_KEY)
    if setting is None:
        setting = AppSetting(key=ALERT_STATE_KEY, value=value)
        db.add(setting)
    else:
        setting.value = value
    await db.commit()


async def check_and_notify(
    db: AsyncSession, *, force: bool = False, dry_run: bool = False
) -> dict:
    admin_settings = await get_admin_settings(db)
    snapshot = await safe_snapshot(db)
    alerts = evaluate_alerts(snapshot, admin_settings)
    state = await _load_state(db)
    now = datetime.now(UTC)
    last_sent_raw = state.get("last_sent_at")
    last_codes = set(state.get("codes") or [])
    cooldown = int(admin_settings.get("alertCooldownMinutes") or 30)
    last_sent = None
    if last_sent_raw:
        try:
            last_sent = datetime.fromisoformat(str(last_sent_raw))
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=UTC)
        except ValueError:
            last_sent = None
    in_cooldown = bool(
        last_sent and now - last_sent < timedelta(minutes=cooldown) and not force
    )
    current_codes = {item["code"] for item in alerts}
    new_codes = current_codes - last_codes
    recovered = sorted(last_codes - current_codes)

    should_send = bool(alerts) and not in_cooldown and (not last_codes or new_codes)
    if not alerts and last_codes and not in_cooldown:
        should_send = True

    delivered = {"ok": False, "skipped": True, "reason": "no change"}
    if should_send and not dry_run:
        if not admin_settings.get("alertPush", True):
            delivered = {"ok": False, "skipped": True, "reason": "alertPush disabled"}
        else:
            delivered = await send_text(
                db, format_alert_text(alerts, recovered=recovered if not alerts else None)
            )
    elif should_send and dry_run:
        delivered = {"ok": False, "skipped": True, "reason": "dry_run"}

    if delivered.get("ok") or dry_run:
        await _save_state(
            db,
            {
                "last_sent_at": now.isoformat(),
                "codes": sorted(current_codes),
                "last_result": delivered,
            },
        )
    log.info(
        "alert_check",
        alerts=len(alerts),
        new=len(new_codes),
        sent=bool(delivered.get("ok")),
        recovered=recovered,
    )
    return {
        "snapshot": snapshot,
        "alerts": alerts,
        "new_codes": sorted(new_codes),
        "recovered": recovered,
        "in_cooldown": in_cooldown,
        "delivered": delivered,
    }
