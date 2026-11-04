from app.services.alert_service import evaluate_alerts, format_alert_text


def base_settings(**overrides):
    return {
        "alertQueueBacklog": 100,
        "alertQueuedMinutes": 30,
        "alertDiskPct": 85,
        "alertBackupHours": 26,
        **overrides,
    }


def test_healthy_snapshot_has_no_alerts():
    alerts = evaluate_alerts(
        {
            "db": "ok",
            "queued_jobs": 2,
            "oldest_queued_minutes": 1,
            "failed_jobs_1h": 0,
            "failing_tasks": [],
            "providers": [{"code": "beike_api", "status": "ok"}],
            "disk": {"path": "/", "used_pct": 40},
            "backup": {"configured": True, "latest_age_hours": 2, "marker": {}},
        },
        base_settings(),
    )
    assert alerts == []


def test_queue_disk_backup_and_source_alerts():
    alerts = evaluate_alerts(
        {
            "db": "ok",
            "queued_jobs": 300,
            "oldest_queued_minutes": 45,
            "failed_jobs_1h": 5,
            "failing_tasks": [{"task_id": 1, "name": "5号线", "last_error": "403"}],
            "providers": [
                {
                    "code": "tianditu",
                    "status": "error",
                    "circuit_open_until": "2026-11-04T04:00:00+00:00",
                    "last_error": "403",
                }
            ],
            "disk": {"path": "/", "used_pct": 96},
            "backup": {
                "configured": True,
                "latest_age_hours": 40,
                "marker": {"status": "failed", "error": "pg_dump failed"},
            },
        },
        base_settings(),
    )
    codes = {item["code"] for item in alerts}
    assert {
        "queue_backlog",
        "queue_stale",
        "job_failures",
        "source_failed:1",
        "provider_circuit:tianditu",
        "disk_high",
        "backup_failed",
        "backup_stale",
    } <= codes
    critical = [item for item in alerts if item["severity"] == "critical"]
    assert [item["code"] for item in critical] == sorted(
        [item["code"] for item in critical],
        key=lambda code: 0,
    )
    assert any(item["code"] == "disk_high" and item["severity"] == "critical" for item in alerts)


def test_configured_backup_dir_without_dump_alerts():
    alerts = evaluate_alerts(
        {
            "db": "ok",
            "queued_jobs": 0,
            "failing_tasks": [],
            "providers": [],
            "disk": None,
            "backup": {
                "configured": True,
                "dir": "/backups",
                "latest_age_hours": None,
                "marker": {},
            },
        },
        base_settings(),
    )
    assert [item["code"] for item in alerts] == ["backup_missing"]


def test_db_error_is_critical_and_missing_backup_is_quiet():
    alerts = evaluate_alerts(
        {
            "db": "error",
            "queued_jobs": 0,
            "failing_tasks": [],
            "providers": [],
            "disk": None,
            "backup": {"configured": False, "latest_age_hours": None, "marker": {}},
        },
        base_settings(),
    )
    assert [item["code"] for item in alerts] == ["db_unavailable"]


def test_format_alert_text_contains_code_and_recovery():
    text = format_alert_text(
        [{"code": "disk_high", "severity": "warning", "message": "磁盘 90%"}],
        recovered=["queue_backlog"],
    )
    assert "disk_high" in text
    assert "queue_backlog" in text
    assert "RentRadar" in text
