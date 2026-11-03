from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_ip, require_admin
from app.core.db import get_db
from app.models import User
from app.schemas.p2 import (
    CityUpdate,
    ReferenceRentImport,
    ShareLinkCreate,
    SourceUpdate,
    TaskCreate,
    TaskUpdate,
)
from app.services import (
    alert_service,
    auth_service,
    catalog_service,
    reference_rent_service,
    share_service,
    task_service,
)
from app.services.settings_service import get_admin_settings

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-p2"],
    dependencies=[Depends(require_admin)],
)


@router.get("/ops/status")
async def ops_status(db: AsyncSession = Depends(get_db)) -> dict:
    snapshot = await alert_service.safe_snapshot(db)
    admin_settings = await get_admin_settings(db)
    return {
        "snapshot": snapshot,
        "alerts": alert_service.evaluate_alerts(snapshot, admin_settings),
        "state": await alert_service.get_state(db),
        "settings": {
            "alertPush": admin_settings.get("alertPush"),
            "alertIntervalMinutes": admin_settings.get("alertIntervalMinutes"),
        },
    }


@router.post("/ops/check")
async def ops_check(
    request: Request,
    force: bool = False,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await alert_service.check_and_notify(db, force=force)
    await auth_service.audit(
        db,
        user=user,
        action="ops.alert_check",
        target="alerts",
        detail={"alerts": [item["code"] for item in result["alerts"]]},
        ip=request_ip(request),
    )
    return result


@router.get("/share-links")
async def share_links(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await share_service.list_links(db)


@router.post("/share-links", status_code=201)
async def create_share_link(
    payload: ShareLinkCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    link = await share_service.create_link(
        db,
        label=payload.label,
        expires_days=payload.expiresDays,
        user_id=user.id,
    )
    await auth_service.audit(
        db,
        user=user,
        action="share.create",
        target=str(link["id"]),
        detail={"label": link["label"], "expires_at": str(link["expires_at"])},
        ip=request_ip(request),
    )
    return link


@router.delete("/share-links/{link_id}")
async def revoke_share_link(
    link_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    link = await share_service.revoke_link(db, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    await auth_service.audit(
        db,
        user=user,
        action="share.revoke",
        target=str(link_id),
        detail={},
        ip=request_ip(request),
    )
    return link


@router.get("/sources")
async def sources(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await catalog_service.list_sources(db)


@router.patch("/sources/{code}")
async def update_source(
    code: str,
    payload: SourceUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = await catalog_service.update_source(db, code, payload.enabled)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    await auth_service.audit(
        db,
        user=user,
        action="source.update",
        target=code,
        detail={"enabled": payload.enabled},
        ip=request_ip(request),
    )
    return source


@router.get("/cities")
async def cities(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await catalog_service.city_health(db)


@router.patch("/cities/{code}")
async def update_city(
    code: str,
    payload: CityUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    city = await catalog_service.update_city(db, code, payload.enabled)
    if city is None:
        raise HTTPException(status_code=404, detail="city not found")
    await auth_service.audit(
        db,
        user=user,
        action="city.update",
        target=code,
        detail={"enabled": payload.enabled},
        ip=request_ip(request),
    )
    return city


@router.post("/tasks", status_code=201)
async def create_task(
    payload: TaskCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        task = await task_service.create_task(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await auth_service.audit(
        db,
        user=user,
        action="task.create",
        target=str(task["id"]),
        detail={
            "city": payload.cityCode,
            "source": payload.sourceCode,
            "enabled": payload.enabled,
        },
        ip=request_ip(request),
    )
    return task


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    task = await task_service.update_task(
        db, task_id, payload.model_dump(exclude_unset=True)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    await auth_service.audit(
        db,
        user=user,
        action="task.update",
        target=str(task_id),
        detail=payload.model_dump(exclude_unset=True),
        ip=request_ip(request),
    )
    return task


@router.delete("/tasks/{task_id}")
async def disable_task(
    task_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    task = await task_service.disable_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    await auth_service.audit(
        db,
        user=user,
        action="task.disable",
        target=str(task_id),
        detail={},
        ip=request_ip(request),
    )
    return task


@router.get("/reference-rents")
async def reference_rents(
    city: str | None = None,
    layout: str | None = None,
    limit: int = 200,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await reference_rent_service.list_references(
        db, city_code=city, layout=layout, limit=limit
    )


@router.post("/reference-rents/import", status_code=201)
async def import_reference_rents(
    payload: ReferenceRentImport,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await reference_rent_service.import_rows(
            db, payload.cityCode, [row.model_dump() for row in payload.rows]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await auth_service.audit(
        db,
        user=user,
        action="reference_rent.import",
        target=payload.cityCode,
        detail=result,
        ip=request_ip(request),
    )
    return result


@router.delete("/reference-rents/{reference_id}")
async def delete_reference_rent(
    reference_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not await reference_rent_service.delete_reference(db, reference_id):
        raise HTTPException(status_code=404, detail="reference not found")
    await auth_service.audit(
        db,
        user=user,
        action="reference_rent.delete",
        target=str(reference_id),
        detail={},
        ip=request_ip(request),
    )
    return {"ok": True}
