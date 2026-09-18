from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from pathlib import Path
import logging
import time
import traceback

from app.config import settings
from app.database.connection import engine, Base, get_db, ensure_tables, check_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("lifeos")
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s | env=%s", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    logger.info("DATABASE_URL set: %s", "yes" if __import__("os").environ.get("DATABASE_URL") else "no (using default)")
    try:
        ok = ensure_tables()
        logger.info("Tables ready: %s", ok)
    except Exception as e:
        logger.error("Startup DB error (will retry on request): %s", e)
        logger.error(traceback.format_exc())
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)

origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in origins else origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
templates_dir = BASE_DIR / "templates"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

from app.routers import auth, dashboard, habits, tasks, goals, finance, profile, statistics, admin  # noqa: E402
from app.security.auth import get_current_user  # noqa: E402

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(habits.router)
app.include_router(tasks.router)
app.include_router(goals.router)
app.include_router(finance.router)
app.include_router(profile.router)
app.include_router(statistics.router)
app.include_router(admin.router)


@app.get("/health")
async def health_check():
    db_status = check_db_connection()
    return {
        "status": "ok" if db_status.get("ok") else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "database": db_status,
    }


@app.get("/", response_class=HTMLResponse)
async def welcome_page(request: Request, db: Session = Depends(get_db)):
    ensure_tables()
    links = {}
    try:
        user = get_current_user(request, db)
        if user:
            return RedirectResponse("/dashboard", status_code=303)
        from app.database.models import SocialLink
        links = {
            s.platform: s
            for s in db.query(SocialLink).filter(SocialLink.is_enabled == True).all()
            if s.url
        }
    except Exception as e:
        logger.warning("Welcome DB: %s", e)

    return templates.TemplateResponse(
        "welcome.html",
        {
            "request": request,
            "app_name": settings.APP_NAME,
            "app_version": settings.APP_VERSION,
            "social": links,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled on %s: %s", request.url.path, exc)
    # Always return something readable
    detail = "Internal server error"
    if settings.ENVIRONMENT != "production":
        detail = f"{type(exc).__name__}: {exc}"
    return JSONResponse(status_code=500, content={"detail": detail})
