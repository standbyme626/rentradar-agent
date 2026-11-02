from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_ip, require_admin
from app.core.db import get_db
from app.models import User
from app.schemas.providers import (
    ProviderCallOut,
    ProviderOut,
    ProviderPatch,
    ProviderTestResultOut,
    ProviderUsageOut,
)
from app.services import auth_service, provider_service

router = APIRouter(
    prefix="/api/admin",
    tags=["providers"],
    dependencies=[Depends(require_admin)],
)


@router.get("/providers", response_model=list[ProviderOut])
async def list_providers(
    domain: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await provider_service.list_providers(db, domain)


@router.get("/providers/{code}", response_model=ProviderOut)
async def get_provider(code: str, db: AsyncSession = Depends(get_db)) -> dict:
    provider = await provider_service.get_provider(db, code)
    if provider is None:
        raise HTTPException(status_code=404, detail="provider not found")
    return provider


@router.patch("/providers/{code}", response_model=ProviderOut)
async def update_provider(
    code: str,
    payload: ProviderPatch,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    provider = await provider_service.update_provider_setting(
        db, code, enabled=payload.enabled, priority=payload.priority
    )
    if provider is None:
        raise HTTPException(status_code=404, detail="provider not found")
    await auth_service.audit(
        db,
        user=user,
        action="provider.update",
        target=code,
        detail=payload.model_dump(exclude_unset=True),
        ip=request_ip(request),
    )
    return provider


@router.post("/providers/{code}/test", response_model=ProviderTestResultOut)
async def test_provider(
    code: str,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await provider_service.test_provider(db, code)
    if result is None:
        raise HTTPException(status_code=404, detail="provider not found")
    await auth_service.audit(
        db,
        user=user,
        action="provider.test",
        target=code,
        detail={"ok": result.get("ok"), "quota_units": result.get("quota_units")},
        ip=request_ip(request),
    )
    return result


@router.get("/providers/{code}/usage", response_model=list[ProviderUsageOut])
async def provider_usage(code: str, db: AsyncSession = Depends(get_db)) -> list[dict]:
    if await provider_service.get_provider(db, code) is None:
        raise HTTPException(status_code=404, detail="provider not found")
    return await provider_service.list_usage(db, code)


@router.get("/provider-calls", response_model=list[ProviderCallOut])
async def provider_calls(
    provider: str | None = None,
    status: str | None = Query(default=None, pattern="^(ok|error)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await provider_service.list_calls(
        db, provider=provider, status=status, limit=limit
    )
