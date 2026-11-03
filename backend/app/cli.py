import argparse
import asyncio
import getpass
import json

from sqlalchemy import func, select, text

from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models import Base, City, Event, Job, Listing, Source, Task, User
from app.services.crawl_service import run_task
from app.services.delivery_service import probe_community, probe_for_listing
from app.services.digest_service import send_digest
from app.services.enrich_service import enrich_task, rescore_task
from app.services.seed_service import seed
from app.services.settings_service import set_commute_destination
from app.services.shard_service import (
    crawl_commands,
    fetch_line_total,
    normalize_page_size,
    probe_shards,
)
from app.sources.base import SourceError
from app.sources.beike_filters import build_line_shards, fetch_filter_config


async def cmd_seed() -> None:
    async with SessionLocal() as db:
        result = await seed(db)
    print(result)


async def cmd_check() -> None:
    async with SessionLocal() as db:
        await db.execute(text("SELECT 1"))
        counts = {}
        for name, model in [
            ("cities", City),
            ("sources", Source),
            ("tasks", Task),
            ("listings", Listing),
            ("events", Event),
            ("jobs", Job),
        ]:
            counts[name] = int(await db.scalar(select(func.count()).select_from(model)) or 0)
    print({"db": "ok", **counts})


async def cmd_create_all() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("schema created (dev fallback; prefer alembic upgrade head)")


async def cmd_crawl(args) -> None:
    async with SessionLocal() as db:
        task = await db.get(Task, args.task_id)
        if task is None:
            print({"error": f"task {args.task_id} not found"})
            return
        result = await run_task(
            db,
            task,
            pages=args.pages,
            sort=args.sort,
            district=args.district,
            line=args.line,
            notify=args.notify,
            full_scan=args.full_scan,
            transport=args.transport,
        )
    print(result)


async def cmd_enrich(args) -> None:
    async with SessionLocal() as db:
        task = await db.get(Task, args.task_id)
        if task is None:
            print({"error": f"task {args.task_id} not found"})
            return
        stats = await enrich_task(db, task, limit=args.limit)
        rescore = await rescore_task(db, task)
    print({"enrich": stats, "rescore": rescore})


async def cmd_set_destination(args) -> None:
    async with SessionLocal() as db:
        value = await set_commute_destination(
            db, args.address, city=args.city, example=args.example
        )
    print({key: value.get(key) for key in ("address", "lng", "lat", "example")})


async def cmd_rescore(args) -> None:
    async with SessionLocal() as db:
        task = await db.get(Task, args.task_id)
        if task is None:
            print({"error": f"task {args.task_id} not found"})
            return
        result = await rescore_task(db, task, limit=args.limit)
    print(result)


async def cmd_digest(args) -> None:
    async with SessionLocal() as db:
        result = await send_digest(db, dry_run=args.dry_run)
    print(result)


async def _password(value: str | None) -> str:
    if value:
        return value
    first = getpass.getpass("password: ")
    second = getpass.getpass("password again: ")
    if first != second:
        raise SystemExit("passwords do not match")
    return first


async def cmd_create_user(args) -> None:
    password = await _password(args.password)
    if len(password) < 8:
        raise SystemExit("password must be at least 8 characters")
    async with SessionLocal() as db:
        await db.execute(
            text(
                "SELECT setval(pg_get_serial_sequence('users','id'), "
                "COALESCE((SELECT max(id) FROM users), 1))"
            )
        )
        await db.commit()
        existing = await db.scalar(select(User).where(User.username == args.username))
        if existing is not None:
            print({"error": f"user {args.username} already exists"})
            return
        user = User(
            username=args.username,
            password_hash=hash_password(password),
            role=args.role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    print({"user": user.username, "role": user.role, "id": user.id})


async def cmd_set_password(args) -> None:
    password = await _password(args.password)
    if len(password) < 8:
        raise SystemExit("password must be at least 8 characters")
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == args.username))
        if user is None:
            print({"error": f"user {args.username} not found"})
            return
        user.password_hash = hash_password(password)
        user.is_active = True
        await db.commit()
    print({"user": args.username, "password": "updated"})


async def cmd_bootstrap_admin(args) -> None:
    password = await _password(args.password)
    if len(password) < 8:
        raise SystemExit("password must be at least 8 characters")
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.username == args.username))
        if user is None:
            user = await db.get(User, 1)
            if user is not None and user.password_hash == "disabled":
                conflict = await db.scalar(
                    select(User).where(User.username == args.username)
                )
                if conflict is None:
                    user.username = args.username
                    user.role = "admin"
                    user.password_hash = hash_password(password)
                    user.is_active = True
                    await db.commit()
                    print({"user": user.username, "role": user.role, "id": user.id})
                    return
            user = User(
                username=args.username,
                password_hash=hash_password(password),
                role="admin",
                is_active=True,
            )
            db.add(user)
        else:
            user.password_hash = hash_password(password)
            user.role = "admin"
            user.is_active = True
        await db.commit()
        await db.refresh(user)
        print({"user": user.username, "role": user.role, "id": user.id})


async def cmd_list_users(_args) -> None:
    async with SessionLocal() as db:
        users = (await db.execute(select(User).order_by(User.id))).scalars().all()
    for user in users:
        print(
            {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "active": bool(user.is_active),
                "password_set": user.password_hash != "disabled",
            }
        )


async def cmd_probe(args) -> None:
    async with SessionLocal() as db:
        if args.community_id:
            result = await probe_community(
                db, args.community_id, args.platform, navigate=not args.no_navigate
            )
        else:
            result = await probe_for_listing(db, args.listing_id)
    print(result)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _print_shard_report(output: dict) -> None:
    line = output["line"]
    print(
        f"{line['name']}（{line['condition']}）· 站点 {output['stations']}/"
        f"{output['total_stations']}"
    )
    summary = output.get("summary")
    sampled = output["stations"] < output["total_stations"]
    if summary:
        print(f"{'站点':<10}{'total':>7}{'页数':>6}{'已抓':>6}{'新增':>6}{'重复':>6}  状态")
        for item in output["shards"]:
            status = "完整" if item["complete"] else (item["missing_reason"] or "未完成")
            total = item["total"] if item["total"] is not None else "—"
            print(
                f"{item['station']:<10}{total:>7}{item['pages']:>6}{item['fetched']:>6}"
                f"{item['unique']:>6}{item['overlap']:>6}  {status}"
            )
        print(
            f"汇总：scope total={summary['scope_total']}，已抓={summary['fetched']}，"
            f"去重后={summary['unique']}，重复={summary['duplicates']}，"
            f"{'抽样' if sampled else ''}覆盖={_pct(summary['coverage_vs_scope'])}"
        )
        line_total = summary["line_total"]
        if line_total is not None:
            print(
                f"线路 total={line_total}，分片合计={summary['scope_total']}，"
                f"{'抽样' if sampled else '线路'}覆盖率={_pct(summary['coverage_vs_line'])}"
            )
        print(
            f"完整分片 {summary['complete_shards']}/{summary['shards']}，"
            f"预计总页数 {summary['expected_pages']}"
        )
    else:
        for item in output["shards"]:
            print(f"{item['name']:<10}{item['condition']}")
    print("逐站采集命令（--full-scan 只用于已确认完整的分片）：")
    for item in output["commands"]:
        print(f"  {item['command']}")


def _shard_error(exc: Exception, as_json: bool) -> None:
    payload = {"error": str(exc)}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(payload)


async def cmd_shards(args) -> None:
    try:
        config = await fetch_filter_config(args.city)
        plan = build_line_shards(config, args.line)
    except SourceError as exc:
        _shard_error(exc, args.json)
        return

    shards = plan["shards"]
    if args.stations > 0:
        shards = shards[: args.stations]
    page_size = normalize_page_size(args.page_size)
    summary = None
    probe_results = None
    if args.probe:
        try:
            line_total = await fetch_line_total(
                plan["line_condition"], city_code=args.city, sort=args.sort
            )
            report = await probe_shards(
                plan,
                shards,
                city_code=args.city,
                pages=args.pages,
                sort=args.sort,
                page_size=page_size,
                line_total=line_total,
            )
        except SourceError as exc:
            _shard_error(exc, args.json)
            return
        summary = report["summary"]
        probe_results = report["shards"]

    output = {
        "line": {
            "id": plan["line_id"],
            "name": plan["line_name"],
            "condition": plan["line_condition"],
        },
        "stations": len(shards),
        "total_stations": len(plan["shards"]),
        "summary": summary,
        "shards": probe_results or shards,
        "commands": crawl_commands(
            shards,
            task_id=args.task_id,
            page_size=page_size,
            results=probe_results,
        ),
    }
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print_shard_report(output)


def main() -> None:
    parser = argparse.ArgumentParser(prog="rentradar")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="insert demo data")
    sub.add_parser("check", help="check DB and row counts")
    sub.add_parser("create-all", help="create schema without alembic (dev)")
    crawl = sub.add_parser("crawl", help="run a beike crawl task through the controlled Chrome")
    crawl.add_argument("--task-id", type=int, required=True)
    crawl.add_argument("--pages", type=int, default=1)
    crawl.add_argument("--sort", choices=["default", "newest"], default="newest")
    crawl.add_argument("--district", default="")
    crawl.add_argument("--line", default="", help="Beike subway line id, e.g. li110460696")
    crawl.add_argument(
        "--transport",
        choices=["cdp", "api"],
        default="",
        help="override task transport; api = Beike app list API, cdp = controlled Chrome",
    )
    crawl.add_argument("--notify", action="store_true")
    crawl.add_argument("--full-scan", action="store_true")
    enrich = sub.add_parser("enrich", help="geocode, POI, commute and rescore")
    enrich.add_argument("--task-id", type=int, required=True)
    enrich.add_argument("--limit", type=int, default=100)
    destination = sub.add_parser("set-destination", help="set commute destination")
    destination.add_argument("--address", required=True)
    destination.add_argument("--city", default="深圳")
    destination.add_argument("--example", action="store_true")
    rescore = sub.add_parser("rescore", help="rescore listings for a task")
    rescore.add_argument("--task-id", type=int, required=True)
    rescore.add_argument("--limit", type=int, default=2000)
    digest = sub.add_parser("digest", help="send or preview the daily digest")
    digest.add_argument("--dry-run", action="store_true")
    probe = sub.add_parser("probe", help="run a Meituan delivery probe on the iPhone")
    probe.add_argument("--community-id", type=int)
    probe.add_argument("--listing-id", type=int)
    probe.add_argument("--platform", default="meituan")
    probe.add_argument("--no-navigate", action="store_true")
    create_user = sub.add_parser("create-user", help="create a login user")
    create_user.add_argument("--username", required=True)
    create_user.add_argument("--password")
    create_user.add_argument("--role", choices=["admin", "viewer"], default="viewer")
    set_password = sub.add_parser("set-password", help="reset a user password")
    set_password.add_argument("--username", required=True)
    set_password.add_argument("--password")
    bootstrap = sub.add_parser("bootstrap-admin", help="create or repair the first admin")
    bootstrap.add_argument("--username", default="admin")
    bootstrap.add_argument("--password")
    sub.add_parser("list-users", help="list login users")
    shards = sub.add_parser(
        "shards", help="generate and probe per-station conditions for a subway line"
    )
    shards.add_argument(
        "--line", required=True, help="line id/name/pinyin, e.g. 5号线 or li110460696"
    )
    shards.add_argument("--city", default="sz")
    shards.add_argument("--stations", type=int, default=0, help="first N stations only; 0 = all")
    shards.add_argument(
        "--pages", type=int, default=1, help="pages per shard; 0 = cover each total"
    )
    shards.add_argument("--page-size", type=int, default=30, help="App API page size (max 30)")
    shards.add_argument("--sort", choices=["default", "newest"], default="newest")
    shards.add_argument("--task-id", type=int, default=1, help="task id used in generated commands")
    shards.add_argument(
        "--probe", action="store_true", help="call the App API to measure totals and de-duplication"
    )
    shards.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.command == "probe" and not (args.community_id or args.listing_id):
        parser.error("probe requires --community-id or --listing-id")
    if args.command == "shards" and (args.stations < 0 or args.pages < 0):
        parser.error("shards requires --stations >= 0 and --pages >= 0")
    if args.command == "seed":
        asyncio.run(cmd_seed())
    elif args.command == "check":
        asyncio.run(cmd_check())
    elif args.command == "crawl":
        asyncio.run(cmd_crawl(args))
    elif args.command == "enrich":
        asyncio.run(cmd_enrich(args))
    elif args.command == "set-destination":
        asyncio.run(cmd_set_destination(args))
    elif args.command == "rescore":
        asyncio.run(cmd_rescore(args))
    elif args.command == "digest":
        asyncio.run(cmd_digest(args))
    elif args.command == "probe":
        asyncio.run(cmd_probe(args))
    elif args.command == "shards":
        asyncio.run(cmd_shards(args))
    elif args.command == "create-user":
        asyncio.run(cmd_create_user(args))
    elif args.command == "set-password":
        asyncio.run(cmd_set_password(args))
    elif args.command == "bootstrap-admin":
        asyncio.run(cmd_bootstrap_admin(args))
    elif args.command == "list-users":
        asyncio.run(cmd_list_users(args))
    else:
        asyncio.run(cmd_create_all())


if __name__ == "__main__":
    main()
