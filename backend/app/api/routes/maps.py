from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import User
from app.services import map_service, transit_service

router = APIRouter(
    prefix="/api/maps", tags=["maps"], dependencies=[Depends(get_current_user)]
)


@router.get("/communities")
async def communities(
    limit: int = 800,
    max_commute: float | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await map_service.communities(db, limit=limit, max_commute=max_commute)


@router.get("/stations")
async def stations(db: AsyncSession = Depends(get_db)) -> dict:
    return await transit_service.ensure_catalog(db)


@router.get("/tiles/{layer}/{z}/{x}/{y}")
async def tile(
    layer: str,
    z: int,
    x: int,
    y: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    content, content_type, cache_state = await map_service.get_tile(db, layer, z, x, y)
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=2592000",
            "X-Tile-Cache": cache_state,
            "X-Tile-Source": "tianditu",
        },
    )


@router.get("/tiles/stats/cache")
async def tile_cache_stats(_: Request, user: User = Depends(get_current_user)) -> dict:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return map_service.tile_cache_stats()
