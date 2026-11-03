"""Cover-image pipeline and fake-listing signals (P1/W5).

Beike's list API exposes one cover image per listing; detail galleries are not
available.  The MVP therefore downloads/caches the cover, computes a 64-bit
difference hash, and combines it with deterministic local signals (duplicate
cover, price outlier, agency wording).  Visual/VL tags are intentionally not
called by default: no vision model is approved, so ``needs_vision`` stays true
and the admin page says so instead of showing invented labels.
"""

import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from urllib.parse import urlparse

import httpx
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models import (
    Listing,
    ListingImage,
    ListingImageAnalysis,
    ListingStatus,
)

log = get_logger("images")

DUPLICATE_DISTANCE = 10  # Hamming distance on 64-bit dHash
AGENCY_KEYWORDS = (
    "公寓",
    "床位",
    "合租",
    "押一付一",
    "免押",
    "直租",
    "转租",
    "个人房源",
    "无中介费",
    "整栋",
    "集中式",
)
MAX_BATCH = 200
# Only the Beike/Lianjia image CDN is expected here; anything else is skipped so
# a manipulated listing URL cannot make the worker fetch arbitrary hosts (SSRF).
ALLOWED_IMAGE_HOSTS = ("ke-image.ljcdn.com",)
ALLOWED_IMAGE_SUFFIXES = (".ljcdn.com",)


def _cache_dir() -> Path:
    path = Path(settings.image_cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def dhash(image: Image.Image) -> str:
    """64-bit difference hash as 16 hex chars; stable across formats."""
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.tobytes())
    bits = 0
    index = 0
    for row in range(8):
        row_start = row * 9
        for col in range(8):
            left = pixels[row_start + col]
            right = pixels[row_start + col + 1]
            bits |= 1 << index if left > right else 0
            index += 1
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    try:
        return (int(a, 16) ^ int(b, 16)).bit_count()
    except (TypeError, ValueError):
        return 64


def image_quality(image: Image.Image) -> dict:
    width, height = image.size
    gray = image.convert("L")
    sample = gray.resize((32, 32), Image.Resampling.BILINEAR)
    values = list(sample.tobytes())
    brightness = round(sum(values) / len(values) / 255, 2)
    return {
        "width": width,
        "height": height,
        "aspect": round(width / height, 3) if height else None,
        "brightness": brightness,
        "low_resolution": width < 480 or height < 360,
        "very_dark": brightness < 0.18,
        "very_bright": brightness > 0.92,
    }


def _cover_url(listing: Listing) -> str | None:
    url = (listing.image_url or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_IMAGE_HOSTS and not host.endswith(ALLOWED_IMAGE_SUFFIXES):
        return None
    return url


async def _download(url: str, listing_id: int, kind: str = "cover") -> tuple[Path, bytes, str]:
    digest = hashlib.sha256(url.encode()).hexdigest()[:16]
    target_dir = _cache_dir() / str(listing_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    for existing in target_dir.glob(f"{kind}-{digest}.*"):
        if existing.is_file() and existing.stat().st_size:
            return existing, existing.read_bytes(), "image/jpeg"
    headers = {"User-Agent": "RentRadar/0.1 (self-use rental research)"}
    proxy = settings.image_proxy or None
    async with httpx.AsyncClient(
        timeout=settings.image_timeout_seconds,
        follow_redirects=True,
        proxy=proxy,
    ) as client:
        async with client.stream("GET", url, headers=headers) as response:
            if response.status_code >= 400:
                raise ValueError(f"封面下载 HTTP {response.status_code}")
            content_type = (response.headers.get("content-type") or "").split(";")[0]
            if not content_type.startswith("image/"):
                raise ValueError(f"封面不是图片：{content_type or 'unknown'}")
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > settings.image_max_bytes:
                    raise ValueError("封面超过大小上限")
                chunks.append(chunk)
    data = b"".join(chunks)
    if not data:
        raise ValueError("封面为空")
    ext = {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(content_type, ".jpg")
    target = target_dir / f"{kind}-{digest}{ext}"
    target.write_bytes(data)
    return target, data, content_type


def _listing_text(listing: Listing) -> str:
    raw = ""
    try:
        raw = json.dumps(listing.raw or {}, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = ""
    return f"{listing.title or ''} {listing.community_name or ''} {raw}"[:4000]


async def _duplicate_signal(
    db: AsyncSession, listing: Listing, phash: str
) -> dict | None:
    index: dict[int, tuple[str, str]] | None = db.info.get("phash_index")
    if index is None:
        rows = (
            await db.execute(
                select(ListingImage.listing_id, ListingImage.phash, Listing.title).where(
                    ListingImage.kind == "cover",
                    ListingImage.phash.is_not(None),
                )
            )
        ).all()
        index = {
            int(listing_id): (str(value), str(title or ""))
            for listing_id, value, title in rows
            if value
        }
        db.info["phash_index"] = index
    matches = []
    for other_id, (other_hash, title) in index.items():
        if other_id == listing.id:
            continue
        distance = hamming(phash, other_hash)
        if distance <= DUPLICATE_DISTANCE:
            matches.append(
                {"listing_id": other_id, "title": title[:80], "distance": distance}
            )
    if not matches:
        return None
    matches.sort(key=lambda item: item["distance"])
    return {
        "code": "duplicate_image",
        "label": "重复封面",
        "severity": "high",
        "confidence": 0.85 if matches[0]["distance"] <= 4 else 0.7,
        "evidence": {"matches": matches[:5], "threshold": DUPLICATE_DISTANCE},
    }


async def _price_signal(db: AsyncSession, listing: Listing) -> dict | None:
    if not listing.rent or not listing.layout or not listing.community_id:
        return None
    rows = (
        (
            await db.execute(
                select(Listing.rent).where(
                    Listing.community_id == listing.community_id,
                    Listing.layout == listing.layout,
                    Listing.status == ListingStatus.active,
                    Listing.rent.is_not(None),
                    Listing.id != listing.id,
                )
            )
        )
        .scalars()
        .all()
    )
    rents = [int(item) for item in rows if item]
    scope = "同小区同户型"
    if len(rents) < 5:
        if not listing.district:
            return None
        district_rows = (
            (
                await db.execute(
                    select(Listing.rent).where(
                        Listing.city_id == listing.city_id,
                        Listing.district == listing.district,
                        Listing.layout == listing.layout,
                        Listing.status == ListingStatus.active,
                        Listing.rent.is_not(None),
                        Listing.id != listing.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        rents = [int(item) for item in district_rows if item]
        scope = "同区同户型"
    if len(rents) < 5:
        return None
    mid = float(median(rents))
    if mid <= 0:
        return None
    delta = (listing.rent - mid) / mid
    if delta > -0.28:
        return None
    confidence = min(0.9, 0.55 + abs(delta))
    return {
        "code": "price_outlier",
        "label": "价格明显低于中位",
        "severity": "high" if delta <= -0.4 else "medium",
        "confidence": round(confidence, 2),
        "evidence": {
            "scope": scope,
            "median": round(mid),
            "rent": listing.rent,
            "delta_pct": round(delta * 100, 1),
            "samples": len(rents),
        },
    }


def _agency_signal(listing: Listing) -> dict | None:
    text = _listing_text(listing)
    hits = [word for word in AGENCY_KEYWORDS if word in text]
    if not hits:
        return None
    return {
        "code": "agency_wording",
        "label": "中介/公寓话术",
        "severity": "medium",
        "confidence": 0.55,
        "evidence": {"keywords": hits},
    }


def _quality_signals(quality: dict) -> list[dict]:
    signals = []
    if quality.get("low_resolution"):
        signals.append(
            {
                "code": "low_resolution",
                "label": "封面分辨率低",
                "severity": "low",
                "confidence": 0.6,
                "evidence": {
                    "width": quality.get("width"),
                    "height": quality.get("height"),
                },
            }
        )
    if quality.get("very_dark"):
        signals.append(
            {
                "code": "dark_cover",
                "label": "封面过暗",
                "severity": "low",
                "confidence": 0.5,
                "evidence": {"brightness": quality.get("brightness")},
            }
        )
    return signals


def classify(signals: list[dict]) -> tuple[str, float]:
    fake = [item for item in signals if item["code"] not in {"low_resolution", "dark_cover"}]
    if len(fake) >= 2:
        confidence = min(0.92, 0.5 + 0.15 * len(fake))
        return "suspicious", round(confidence, 2)
    if len(fake) == 1:
        return "watch", round(float(fake[0].get("confidence") or 0.5), 2)
    if signals:
        return "clear", 0.5
    return "clear", 0.3


async def analyze_listing(db: AsyncSession, listing: Listing) -> dict:
    url = _cover_url(listing)
    now = datetime.now(UTC)
    record = None
    if url:
        record = await db.scalar(
            select(ListingImage).where(
                ListingImage.listing_id == listing.id,
                ListingImage.kind == "cover",
                ListingImage.url == url,
            )
        )
    if url and record is None:
        record = ListingImage(listing_id=listing.id, kind="cover", url=url)
        db.add(record)
        await db.flush()
    quality: dict = {}
    signals: list[dict] = []
    if url and record is not None:
        try:
            path, data, content_type = await _download(url, listing.id)
            image = Image.open(io.BytesIO(data))
            quality = image_quality(image)
            phash = dhash(image)
            record.local_path = str(path)
            record.content_type = content_type
            record.bytes = len(data)
            record.width = quality["width"]
            record.height = quality["height"]
            record.brightness = quality["brightness"]
            record.phash = phash
            record.phash_bucket = phash[:4]
            record.status = "downloaded"
            record.error = None
            record.downloaded_at = now
            signals.extend(_quality_signals(quality))
            duplicate = await _duplicate_signal(db, listing, phash)
            if duplicate:
                signals.append(duplicate)
        except Exception as exc:  # download/format failure is expected sometimes
            if record is not None:
                record.status = "failed"
                record.error = f"{type(exc).__name__}: {exc}"[:500]
            signals.append(
                {
                    "code": "cover_unavailable",
                    "label": "封面不可用",
                    "severity": "low",
                    "confidence": 0.6,
                    "evidence": {"error": str(exc)[:200]},
                }
            )
    else:
        signals.append(
            {
                "code": "cover_missing",
                "label": "无封面",
                "severity": "low",
                "confidence": 0.5,
                "evidence": {},
            }
        )
    price = await _price_signal(db, listing)
    if price:
        signals.append(price)
    agency = _agency_signal(listing)
    if agency:
        signals.append(agency)
    verdict, confidence = classify(signals)
    analysis = await db.get(ListingImageAnalysis, listing.id)
    if analysis is None:
        analysis = ListingImageAnalysis(listing_id=listing.id)
        db.add(analysis)
    analysis.signals = signals
    analysis.verdict = verdict
    analysis.confidence = confidence
    analysis.quality = quality
    analysis.needs_vision = not settings.image_vision_enabled
    analysis.analyzed_at = now
    await db.commit()
    db.info.pop("phash_index", None)
    return {
        "listing_id": listing.id,
        "status": record.status if record else "missing",
        "signals": signals,
        "verdict": verdict,
        "confidence": confidence,
        "quality": quality,
    }


async def batch_analyze(
    db: AsyncSession,
    *,
    listing_ids: list[int] | None = None,
    limit: int = 50,
) -> dict:
    cap = MAX_BATCH
    limit = max(1, min(int(limit or cap), cap, MAX_BATCH))
    stmt = (
        select(Listing)
        .where(
            Listing.status == ListingStatus.active,
            Listing.image_url.is_not(None),
        )
        .order_by(Listing.score.desc().nullslast(), Listing.id.desc())
        .limit(limit)
    )
    if listing_ids:
        stmt = stmt.where(Listing.id.in_([int(item) for item in listing_ids][:limit]))
    else:
        analyzed = (
            select(ListingImageAnalysis.listing_id)
            .where(ListingImageAnalysis.listing_id == Listing.id)
            .exists()
        )
        stmt = stmt.where(~analyzed)
    listings = (await db.execute(stmt)).scalars().all()
    stats = {
        "requested": len(listings),
        "analyzed": 0,
        "failed": 0,
        "suspicious": 0,
        "watch": 0,
        "vision_pending": 0,
        "duplicates": 0,
    }
    for listing in listings:
        try:
            result = await analyze_listing(db, listing)
        except Exception as exc:  # one bad row must not kill the batch
            await db.rollback()
            stats["failed"] += 1
            log.warning("image_analysis_failed", listing_id=listing.id, error=str(exc)[:200])
            continue
        stats["analyzed"] += 1
        if result["verdict"] == "suspicious":
            stats["suspicious"] += 1
        if result["verdict"] == "watch":
            stats["watch"] += 1
        if any(item["code"] == "duplicate_image" for item in result["signals"]):
            stats["duplicates"] += 1
        if result.get("quality") and settings.image_vision_enabled is False:
            stats["vision_pending"] += 1
    return stats


async def stats(db: AsyncSession) -> dict:
    candidates = int(
        await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active, Listing.image_url.is_not(None))
        )
        or 0
    )
    downloaded = int(
        await db.scalar(
            select(func.count())
            .select_from(ListingImage)
            .where(ListingImage.status == "downloaded")
        )
        or 0
    )
    failed = int(
        await db.scalar(
            select(func.count())
            .select_from(ListingImage)
            .where(ListingImage.status == "failed")
        )
        or 0
    )
    analyzed = int(
        await db.scalar(select(func.count()).select_from(ListingImageAnalysis)) or 0
    )
    suspicious = int(
        await db.scalar(
            select(func.count())
            .select_from(ListingImageAnalysis)
            .where(ListingImageAnalysis.verdict == "suspicious")
        )
        or 0
    )
    watch = int(
        await db.scalar(
            select(func.count())
            .select_from(ListingImageAnalysis)
            .where(ListingImageAnalysis.verdict == "watch")
        )
        or 0
    )
    vision_pending = int(
        await db.scalar(
            select(func.count())
            .select_from(ListingImageAnalysis)
            .where(ListingImageAnalysis.needs_vision.is_(True))
        )
        or 0
    )
    return {
        "candidates": candidates,
        "downloaded": downloaded,
        "failed": failed,
        "analyzed": analyzed,
        "pending": max(0, candidates - analyzed),
        "suspicious": suspicious,
        "watch": watch,
        "vision_pending": vision_pending,
        "vision_enabled": bool(settings.image_vision_enabled),
        "duplicate_distance": DUPLICATE_DISTANCE,
    }


def _image_dict(item: ListingImage) -> dict:
    return {
        "id": item.id,
        "listing_id": item.listing_id,
        "kind": item.kind,
        "url": item.url,
        "local_path": item.local_path,
        "status": item.status,
        "width": item.width,
        "height": item.height,
        "bytes": item.bytes,
        "phash": item.phash,
        "brightness": float(item.brightness) if item.brightness is not None else None,
        "error": item.error,
        "downloaded_at": item.downloaded_at,
    }


async def queue(
    db: AsyncSession,
    *,
    verdict: str | None = None,
    limit: int = 50,
    q: str | None = None,
) -> dict:
    stmt = (
        select(Listing, ListingImage, ListingImageAnalysis)
        .outerjoin(
            ListingImage,
            (ListingImage.listing_id == Listing.id) & (ListingImage.kind == "cover"),
        )
        .outerjoin(
            ListingImageAnalysis, ListingImageAnalysis.listing_id == Listing.id
        )
        .where(
            Listing.status == ListingStatus.active,
            Listing.image_url.is_not(None),
        )
        .order_by(Listing.score.desc().nullslast(), Listing.id.desc())
        .limit(max(1, min(limit, 200)))
    )
    if verdict:
        stmt = stmt.where(ListingImageAnalysis.verdict == verdict)
    if q:
        stmt = stmt.where(
            Listing.community_name.ilike(f"%{q.strip()}%")
            | Listing.title.ilike(f"%{q.strip()}%")
        )
    rows = (await db.execute(stmt)).all()
    return {
        "items": [
            {
                "listing_id": listing.id,
                "title": listing.title,
                "community_name": listing.community_name,
                "district": listing.district,
                "rent": listing.rent,
                "score": listing.score,
                "image_url": listing.image_url,
                "image": _image_dict(image) if image else None,
                "analysis": (
                    {
                        "verdict": analysis.verdict,
                        "confidence": float(analysis.confidence)
                        if analysis.confidence is not None
                        else None,
                        "signals": analysis.signals or [],
                        "quality": analysis.quality or {},
                        "needs_vision": analysis.needs_vision,
                        "analyzed_at": analysis.analyzed_at,
                    }
                    if analysis
                    else None
                ),
            }
            for listing, image, analysis in rows
        ]
    }


async def duplicate_groups(db: AsyncSession, limit: int = 1000) -> list[dict]:
    rows = (
        await db.execute(
            select(ListingImage.listing_id, ListingImage.phash, Listing.title)
            .where(ListingImage.kind == "cover", ListingImage.phash.is_not(None))
            .limit(max(1, min(limit, 5000)))
        )
    ).all()
    items = [
        {"listing_id": int(listing_id), "phash": str(phash), "title": title or ""}
        for listing_id, phash, title in rows
        if phash
    ]
    parent = {item["listing_id"]: item["listing_id"] for item in items}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, item in enumerate(items):
        for other in items[index + 1 :]:
            if hamming(item["phash"], other["phash"]) <= DUPLICATE_DISTANCE:
                union(item["listing_id"], other["listing_id"])
    grouped: dict[int, list[dict]] = {}
    for item in items:
        grouped.setdefault(find(item["listing_id"]), []).append(item)
    groups = [
        {
            "size": len(group),
            "listings": [
                {"listing_id": item["listing_id"], "title": item["title"]}
                for item in group[:20]
            ],
        }
        for group in grouped.values()
        if len(group) > 1
    ]
    groups.sort(key=lambda item: item["size"], reverse=True)
    return groups[:50]


def cached_file(listing_id: int, kind: str = "cover") -> Path | None:
    directory = Path(settings.image_cache_dir) / str(listing_id)
    if not directory.is_dir():
        return None
    for item in directory.glob(f"{kind}-*"):
        if item.is_file() and item.stat().st_size:
            return item
    return None


def resolve_distance(a: str, b: str) -> int:
    return hamming(a, b)


def score_from_signals(signals: list[dict]) -> float:
    """Small helper used by tests/UI: 0-1 risk-ish confidence."""
    if not signals:
        return 0.0
    return round(
        min(1.0, sum(float(item.get("confidence") or 0) for item in signals) / 2), 2
    )
