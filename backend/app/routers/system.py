from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.services.gemini import is_gemini_configured
from app.services.storage import storage_service
import redis.asyncio as aioredis

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    redis_status = "ok"
    minio_status = "ok"

    # Check DB
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
    except Exception as e:
        redis_status = f"error: {str(e)}"

    # Check MinIO
    try:
        storage_service.ensure_bucket_and_cors()
    except Exception as e:
        minio_status = f"error: {str(e)}"

    return {
        "status": "healthy" if db_status == "ok" and redis_status == "ok" else "degraded",
        "database": db_status,
        "redis": redis_status,
        "minio": minio_status,
        "gemini_configured": is_gemini_configured(),
        "whisper_model": settings.WHISPER_MODEL,
        "whisper_device": settings.WHISPER_DEVICE,
    }


@router.get("/ai-status")
async def get_ai_status():
    configured = is_gemini_configured()
    return {
        "is_configured": configured,
        "model": settings.GEMINI_MODEL,
        "instructions": (
            "Gemini is active and evaluating viral candidates."
            if configured
            else "Gemini API key is not configured. Reel Studio is using high-precision heuristic discovery. To enable Gemini AI scoring and title generation, get a key at https://aistudio.google.com/apikey and add GEMINI_API_KEY to your .env file."
        ),
    }
