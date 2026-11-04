from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rate_limit import allow, client_ip
from app.services import share_service

router = APIRouter(prefix="/api/public", tags=["public"])

NOINDEX_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


@router.get("/dashboard/{token}")
async def public_dashboard(
    token: str, request: Request, db: AsyncSession = Depends(get_db)
) -> JSONResponse:
    ip = client_ip(request)
    allowed = await allow(
        f"share:{ip}:{token[:12]}", limit=60, window_seconds=60
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="too many requests")
    link = await share_service.resolve_token(db, token)
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    payload = await share_service.public_dashboard(db)
    return JSONResponse(content=payload, headers=NOINDEX_HEADERS)
