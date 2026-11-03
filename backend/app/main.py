from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin as admin_routes
from app.api.routes import admin_p1 as admin_p1_routes
from app.api.routes import admin_p2 as admin_p2_routes
from app.api.routes import admin_providers, dashboard, health, listings, tasks, ws
from app.api.routes import agent as agent_routes
from app.api.routes import auth as auth_routes
from app.api.routes import maps as maps_routes
from app.api.routes import public as public_routes
from app.api.routes import settings as settings_routes
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging()
log = get_logger("app")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.secret_key == "dev-only-change-me":
        log.warning("insecure_secret_key", hint="set APP_SECRET_KEY in .env")
    log.info("startup", env=settings.env, version=settings.version)
    yield
    log.info("shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth_routes.router)
app.include_router(dashboard.router)
app.include_router(listings.router)
app.include_router(tasks.router)
app.include_router(settings_routes.router)
app.include_router(ws.router)
app.include_router(admin_routes.router)
app.include_router(admin_p1_routes.router)
app.include_router(admin_p2_routes.router)
app.include_router(maps_routes.router)
app.include_router(admin_providers.router)
app.include_router(agent_routes.router)
app.include_router(public_routes.router)

dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist_dir.is_dir():
    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        if not settings.docs_enabled and full_path in {"docs", "redoc", "openapi.json"}:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})
        candidate = (dist_dir / full_path).resolve()
        if candidate.is_file() and dist_dir.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(dist_dir / "index.html")

else:

    @app.get("/")
    async def index() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/health",
        }
