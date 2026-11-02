from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting

COMMUTE_KEY = "commute_destination"
ADMIN_SETTINGS_KEY = "admin_settings"
DEFAULT_ADMIN_SETTINGS = {
    "amapMonthlyCap": 5000,
    "sessionAmapCap": 15,
    "batchCap": 10,
    "aiDailyCap": 500,
    "notifyBatchCap": 10,
    "notifyScoreMin": 75,
    "priceDropPct": 8.0,
    "quietStart": "23:00",
    "quietEnd": "08:00",
    "feishu": True,
    "digest": True,
    "quiet": True,
    "pauseAlert": True,
    "monitorPush": True,
}


async def get_admin_settings(db: AsyncSession) -> dict:
    setting = await db.get(AppSetting, ADMIN_SETTINGS_KEY)
    value = dict(setting.value) if setting and setting.value else {}
    return {**DEFAULT_ADMIN_SETTINGS, **value}


async def update_admin_settings(db: AsyncSession, payload: dict) -> dict:
    value = {**DEFAULT_ADMIN_SETTINGS, **payload}
    setting = await db.get(AppSetting, ADMIN_SETTINGS_KEY)
    if setting is None:
        setting = AppSetting(key=ADMIN_SETTINGS_KEY, value=value)
        db.add(setting)
    else:
        setting.value = value
    await db.commit()
    return value


def _parse_hhmm(value: str | None, fallback: time) -> time:
    try:
        hour, minute = str(value or "").split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except (TypeError, ValueError):
        return fallback


def is_quiet_now(admin_settings: dict, now: datetime | None = None) -> bool:
    if not admin_settings.get("quiet", True):
        return False
    current = (now or datetime.now(ZoneInfo("Asia/Shanghai"))).astimezone(
        ZoneInfo("Asia/Shanghai")
    ).time()
    start = _parse_hhmm(admin_settings.get("quietStart"), time(23, 0))
    end = _parse_hhmm(admin_settings.get("quietEnd"), time(8, 0))
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def destination_key(value: dict | None) -> str | None:
    if not value:
        return None
    lng = value.get("lng")
    lat = value.get("lat")
    if lng is None or lat is None:
        return None
    return f"{lng:.6f},{lat:.6f}"


async def get_commute_destination(db: AsyncSession) -> dict | None:
    setting = await db.get(AppSetting, COMMUTE_KEY)
    return dict(setting.value) if setting and setting.value else None


async def set_commute_destination(
    db: AsyncSession, address: str, city: str = "深圳", example: bool = False
) -> dict:
    from app.integrations.base import Capability
    from app.services import provider_runtime

    geo = await provider_runtime.invoke(
        db,
        Capability.geocode,
        "geocode",
        address,
        city=city,
        cap_key="amapMonthlyCap",
    )
    if geo is None:
        raise ValueError(f"cannot geocode address: {address}")
    value = {
        "address": address,
        "city": city,
        "lng": geo["lng"],
        "lat": geo["lat"],
        "level": geo.get("level"),
        "adcode": geo.get("adcode"),
        "example": example,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    setting = await db.get(AppSetting, COMMUTE_KEY)
    if setting is None:
        setting = AppSetting(key=COMMUTE_KEY, value=value)
        db.add(setting)
    else:
        setting.value = value
    await db.commit()
    return value
