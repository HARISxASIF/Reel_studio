import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.config import settings
from app.database import async_engine, Base
from app.services.storage import storage_service
from app.routers import auth, projects, uploads, reels, system, live, social

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Reel Studio API...")
    # Initialize DB tables if they don't exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS subtitle_font_size INTEGER DEFAULT 58;"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS split_facecam_crop JSON;"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS split_gameplay_crop JSON;"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS split_order VARCHAR(50) DEFAULT 'facecam_top';"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS split_ratio FLOAT DEFAULT 0.35;"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS source_media_key VARCHAR(1024);"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS is_live_clip BOOLEAN DEFAULT FALSE;"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS subtitle_position VARCHAR(50) DEFAULT 'bottom';"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS subtitle_y_percent FLOAT DEFAULT 0.82;"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS subtitle_color VARCHAR(50) DEFAULT '#FFE500';"))
        await conn.execute(text("ALTER TABLE reels ADD COLUMN IF NOT EXISTS subtitle_font_family VARCHAR(100) DEFAULT 'Noto Sans';"))

        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS framing_mode VARCHAR(50) DEFAULT 'crop';"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS pan_x_offset FLOAT DEFAULT 0.0;"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS subtitle_font_size INTEGER DEFAULT 54;"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS subtitle_position VARCHAR(50) DEFAULT 'bottom';"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS subtitle_y_percent FLOAT DEFAULT 0.82;"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS subtitle_color VARCHAR(50) DEFAULT '#FFE500';"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS subtitle_font_family VARCHAR(100) DEFAULT 'Noto Sans';"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS split_facecam_crop JSON;"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS split_gameplay_crop JSON;"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS split_order VARCHAR(50) DEFAULT 'facecam_top';"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS split_ratio FLOAT DEFAULT 0.35;"))
        await conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS settings_snapshot JSON;"))
    logger.info("Database tables initialized and migrated.")

    # Ensure MinIO bucket and CORS configuration
    try:
        storage_service.ensure_bucket_and_cors()
    except Exception as e:
        logger.warning(f"MinIO bucket initialization deferred: {e}")

    yield

    logger.info("Shutting down Reel Studio API...")
    await async_engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

# CORS configuration for browser frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local development with Next.js on port 3000
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register routers
app.include_router(system.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(uploads.router)
app.include_router(reels.router)
app.include_router(live.router)
app.include_router(social.router)


@app.get("/")
async def root():
    return {
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs_url": "/docs",
    }
