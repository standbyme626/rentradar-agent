from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_ip, require_admin
from app.core.db import get_db
from app.models import Community, User
from app.schemas.p1 import (
    AgentEvalRunRequest,
    ImageAnalyzeRequest,
    ReputationExtractRequest,
    ReputationMentionCreate,
    ReputationStatusUpdate,
)
from app.services import (
    admin_service,
    agent_eval_service,
    auth_service,
    image_service,
    reputation_service,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin-p1"],
    dependencies=[Depends(require_admin)],
)


@router.get("/images")
async def images(
    verdict: str | None = None,
    q: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> dict:
    return {
        "stats": await image_service.stats(db),
        "queue": await image_service.queue(db, verdict=verdict, limit=limit, q=q),
        "duplicates": await image_service.duplicate_groups(db),
        "vision_enabled": image_service.settings.image_vision_enabled,
    }


@router.get("/images/{listing_id}/file")
async def image_file(listing_id: int) -> FileResponse:
    path = image_service.cached_file(listing_id)
    if path is None:
        raise HTTPException(status_code=404, detail="cover not cached")
    return FileResponse(path)


@router.post("/images/analyze")
async def analyze_images(
    payload: ImageAnalyzeRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await admin_service.enqueue_image_analysis(
        db, payload.listingIds, limit=payload.limit
    )
    if job is None:
        raise HTTPException(status_code=400, detail="no task available")
    await auth_service.audit(
        db,
        user=user,
        action="images.analyze",
        target=job["id"],
        detail={
            "listing_ids": payload.listingIds[:50],
            "limit": payload.limit,
        },
        ip=request_ip(request),
    )
    return job


@router.get("/reputation")
async def reputation_overview(
    limit: int = 12, db: AsyncSession = Depends(get_db)
) -> dict:
    return await reputation_service.overview(db, limit=limit)


@router.get("/reputation/communities")
async def reputation_communities(
    q: str = "", limit: int = 10, db: AsyncSession = Depends(get_db)
) -> list[dict]:
    return await reputation_service.find_communities(db, q, limit=limit)


@router.get("/reputation/communities/{community_id}")
async def reputation_community(
    community_id: int, db: AsyncSession = Depends(get_db)
) -> dict:
    summary = await reputation_service.community_summary(db, community_id)
    mentions = await reputation_service.mentions_for_community(db, community_id)
    community = await db.get(Community, community_id)
    if community is None:
        raise HTTPException(status_code=404, detail="community not found")
    return {
        "community": {
            "id": community.id,
            "name": community.name,
            "district": community.district,
        },
        "summary": summary,
        "mentions": mentions,
    }


@router.post("/reputation/mentions", status_code=201)
async def create_reputation_mention(
    payload: ReputationMentionCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        mention = await reputation_service.create_mention(
            db,
            payload.communityId,
            {
                "source": payload.source,
                "url": payload.url,
                "title": payload.title,
                "excerpt": payload.excerpt,
                "issue_type": payload.issueType,
                "severity": payload.severity,
                "confidence": payload.confidence,
                "match_status": payload.matchStatus,
                "published_at": payload.publishedAt,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await auth_service.audit(
        db,
        user=user,
        action="reputation.create",
        target=str(mention["id"]),
        detail={"community_id": payload.communityId, "source": payload.source},
        ip=request_ip(request),
    )
    return mention


@router.patch("/reputation/mentions/{mention_id}")
async def update_reputation_mention(
    mention_id: int,
    payload: ReputationStatusUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        mention = await reputation_service.update_match_status(
            db, mention_id, payload.matchStatus
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if mention is None:
        raise HTTPException(status_code=404, detail="mention not found")
    await auth_service.audit(
        db,
        user=user,
        action="reputation.match_status",
        target=str(mention_id),
        detail={"match_status": payload.matchStatus},
        ip=request_ip(request),
    )
    return mention


@router.delete("/reputation/mentions/{mention_id}", status_code=204)
async def delete_reputation_mention(
    mention_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not await reputation_service.delete_mention(db, mention_id):
        raise HTTPException(status_code=404, detail="mention not found")
    await auth_service.audit(
        db,
        user=user,
        action="reputation.delete",
        target=str(mention_id),
        detail={},
        ip=request_ip(request),
    )


@router.post("/reputation/extract")
async def extract_reputation(
    payload: ReputationExtractRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    community = await db.get(Community, payload.communityId)
    if community is None:
        raise HTTPException(status_code=404, detail="community not found")
    drafts = await reputation_service.extract_mentions(
        db, payload.text, community.name
    )
    await auth_service.audit(
        db,
        user=user,
        action="reputation.extract",
        target=str(payload.communityId),
        detail={"drafts": len(drafts)},
        ip=request_ip(request),
    )
    return {
        "community": {"id": community.id, "name": community.name},
        "drafts": drafts,
        "note": "抽取结果仅作草稿；需人工确认来源/链接后录入才会参与评分。",
    }


@router.get("/agent/eval")
async def agent_eval(db: AsyncSession = Depends(get_db)) -> dict:
    return await agent_eval_service.latest(db)


@router.post("/agent/eval/run")
async def run_agent_eval(
    payload: AgentEvalRunRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        result = await agent_eval_service.run_and_store(db, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await auth_service.audit(
        db,
        user=user,
        action="agent.eval_run",
        target=str(result["id"]),
        detail={"passed": result["passed"], "total": result["total"]},
        ip=request_ip(request),
    )
    return result


@router.get("/agent/cost")
async def agent_cost(days: int = 7, db: AsyncSession = Depends(get_db)) -> dict:
    return await agent_eval_service.cost_summary(db, days=days)
