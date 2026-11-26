import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.user import User
from app.models.user_credential import UserCredential
from app.models.project import Project
from app.models.social import SocialAccount
from app.schemas.settings import (
    IntegrationsSettingsResponse,
    GeminiSettingsPayload,
    GeminiTestResponse,
    YouTubeSettingsPayload,
)
from app.services.auth import get_current_user
from app.services.encryption import encrypt_token, decrypt_token
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _mask_secret(secret: Optional[str]) -> Optional[str]:
    """Mask a secret string, revealing only first 4 and last 4 chars."""
    if not secret:
        return None
    s = str(secret).strip()
    if len(s) <= 8:
        return "••••••••"
    return f"{s[:4]}••••••••{s[-4:]}"


async def _get_or_create_credentials(user_id, db: AsyncSession) -> UserCredential:
    result = await db.execute(select(UserCredential).where(UserCredential.user_id == user_id))
    creds = result.scalar_one_or_none()
    if not creds:
        creds = UserCredential(
            user_id=user_id,
            gemini_status="not_configured",
            youtube_status="not_configured",
        )
        db.add(creds)
        await db.commit()
        await db.refresh(creds)
    return creds


def _test_gemini_connectivity(api_key: str, model: str = "gemini-3.5-flash-lite") -> tuple[str, str]:
    """
    Test connectivity to Gemini using official google.genai client.
    Returns (status: str, message: str)
    """
    clean_key = str(api_key).strip()
    if not clean_key:
        return ("invalid", "API key cannot be empty.")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=clean_key)
        # Lightweight test prompt
        test_model = model or "gemini-3.5-flash-lite"
        if "2.5" in test_model:
            test_model = "gemini-3.5-flash-lite"

        res = client.models.generate_content(
            model=test_model,
            contents="Respond with only: OK",
        )
        if res and res.text:
            return ("connected", "Successfully connected to Google AI Studio Gemini API.")
        return ("connected", "API key verified successfully.")
    except Exception as e:
        err_str = str(e).lower()
        if "resource_exhausted" in err_str or "429" in err_str or "rate limit" in err_str or "quota" in err_str:
            return ("quota_exhausted", "Gemini quota exhausted (HTTP 429). Check your Google Cloud billing or rate limits.")
        elif "api_key_invalid" in err_str or "invalid api key" in err_str or "400" in err_str or "unregistered" in err_str:
            return ("invalid", "Invalid Gemini API key. Please check the key created in Google AI Studio (https://aistudio.google.com/apikey).")
        elif "not found" in err_str or "model" in err_str:
            return ("invalid", f"Selected model '{model}' is unavailable for this API key tier.")
        else:
            return ("error", f"Connection test failed: {str(e)[:150]}")


@router.get("/integrations", response_model=IntegrationsSettingsResponse)
async def get_integrations_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Return current user integration status with masked secrets.
    Secrets are never returned in plaintext.
    """
    creds = await _get_or_create_credentials(current_user.id, db)

    # Decrypt and mask Gemini key
    gemini_key_masked = None
    if creds.gemini_api_key_encrypted:
        try:
            raw_key = decrypt_token(creds.gemini_api_key_encrypted)
            gemini_key_masked = _mask_secret(raw_key)
        except Exception:
            gemini_key_masked = "•••••••• (Encrypted)"

    # Decrypt and mask YouTube secret
    youtube_secret_masked = None
    if creds.youtube_client_secret_encrypted:
        try:
            raw_secret = decrypt_token(creds.youtube_client_secret_encrypted)
            youtube_secret_masked = _mask_secret(raw_secret)
        except Exception:
            youtube_secret_masked = "•••••••• (Encrypted)"

    # Compute usage metrics for this user
    storage_res = await db.execute(
        select(func.coalesce(func.sum(Project.source_file_size), 0)).where(
            Project.user_id == current_user.id
        )
    )
    total_bytes = storage_res.scalar() or 0
    storage_used_mb = round(total_bytes / (1024 * 1024), 2)

    active_jobs_res = await db.execute(
        select(func.count(Project.id)).where(
            Project.user_id == current_user.id,
            Project.status.in_(["importing", "probing", "analyzing"]),
        )
    )
    active_jobs_count = active_jobs_res.scalar() or 0

    redirect_uri = settings.YOUTUBE_REDIRECT_URI or f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/social/youtube/callback"

    return IntegrationsSettingsResponse(
        gemini_configured=bool(creds.gemini_api_key_encrypted),
        gemini_key_masked=gemini_key_masked,
        gemini_status=creds.gemini_status or "not_configured",
        gemini_last_tested_at=creds.gemini_last_tested_at,
        gemini_model=creds.gemini_model or "gemini-3.5-flash-lite",
        youtube_configured=bool(creds.youtube_client_id and creds.youtube_client_secret_encrypted),
        youtube_client_id=creds.youtube_client_id,
        youtube_secret_masked=youtube_secret_masked,
        youtube_status=creds.youtube_status or "not_configured",
        youtube_redirect_uri=redirect_uri,
        max_concurrent_jobs=creds.max_concurrent_jobs or 2,
        storage_limit_mb=creds.storage_limit_mb or 10240,
        storage_used_mb=storage_used_mb,
        active_jobs_count=active_jobs_count,
    )


@router.post("/integrations/gemini")
async def update_gemini_settings(
    payload: GeminiSettingsPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save, test connection, or remove user's Gemini API key.
    Stores key encrypted at rest with Fernet.
    """
    creds = await _get_or_create_credentials(current_user.id, db)
    action = payload.action.lower().strip()

    if action == "test":
        # Resolve key to test: either passed in payload or already stored
        key_to_test = payload.api_key
        if not key_to_test and creds.gemini_api_key_encrypted:
            try:
                key_to_test = decrypt_token(creds.gemini_api_key_encrypted)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to decrypt stored key: {e}")

        if not key_to_test:
            raise HTTPException(status_code=400, detail="No Gemini API key provided to test.")

        status_result, msg = _test_gemini_connectivity(key_to_test, payload.model or creds.gemini_model)
        creds.gemini_status = status_result
        creds.gemini_last_tested_at = datetime.utcnow()
        await db.commit()
        return GeminiTestResponse(status=status_result, message=msg)

    elif action == "save":
        if not payload.api_key or not payload.api_key.strip():
            raise HTTPException(status_code=400, detail="Gemini API key cannot be blank.")

        clean_key = payload.api_key.strip()
        # Test key automatically on save to provide immediate feedback
        status_result, msg = _test_gemini_connectivity(clean_key, payload.model or creds.gemini_model)

        creds.gemini_api_key_encrypted = encrypt_token(clean_key)
        creds.gemini_status = status_result
        creds.gemini_last_tested_at = datetime.utcnow()
        if payload.model:
            creds.gemini_model = payload.model
        await db.commit()

        return {
            "status": "saved",
            "connection_status": status_result,
            "message": f"Gemini API key saved. Status: {status_result}. {msg}",
        }

    elif action == "remove":
        creds.gemini_api_key_encrypted = None
        creds.gemini_status = "not_configured"
        creds.gemini_last_tested_at = None
        await db.commit()
        return {"status": "removed", "message": "Gemini API key removed. Reverting to heuristic mode."}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action '{payload.action}'. Use 'save', 'test', or 'remove'.")


@router.post("/integrations/youtube")
async def update_youtube_settings(
    payload: YouTubeSettingsPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Save or remove user's Google Cloud YouTube OAuth Client ID and Secret.
    Stores Client Secret encrypted at rest with Fernet.
    """
    creds = await _get_or_create_credentials(current_user.id, db)
    action = payload.action.lower().strip()

    if action == "save":
        if not payload.client_id or not payload.client_id.strip():
            raise HTTPException(status_code=400, detail="YouTube Client ID is required.")
        if not payload.client_secret or not payload.client_secret.strip():
            raise HTTPException(status_code=400, detail="YouTube Client Secret is required.")

        clean_client_id = payload.client_id.strip()
        clean_client_secret = payload.client_secret.strip()

        # If Client ID changed, identify which existing channels require reconnection
        if creds.youtube_client_id and creds.youtube_client_id != clean_client_id:
            # Mark existing accounts as reconnect_required
            acc_res = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.user_id == current_user.id,
                    SocialAccount.platform == "youtube",
                )
            )
            for acc in acc_res.scalars().all():
                acc.status = "reconnect_required"

        creds.youtube_client_id = clean_client_id
        creds.youtube_client_secret_encrypted = encrypt_token(clean_client_secret)
        creds.youtube_status = "configured"
        await db.commit()

        return {
            "status": "saved",
            "message": "YouTube OAuth credentials successfully saved. You can now connect your YouTube channels.",
        }

    elif action == "remove":
        creds.youtube_client_id = None
        creds.youtube_client_secret_encrypted = None
        creds.youtube_status = "not_configured"

        # Mark YouTube accounts as reconnect_required
        acc_res = await db.execute(
            select(SocialAccount).where(
                SocialAccount.user_id == current_user.id,
                SocialAccount.platform == "youtube",
            )
        )
        for acc in acc_res.scalars().all():
            acc.status = "reconnect_required"

        await db.commit()
        return {"status": "removed", "message": "YouTube OAuth credentials removed."}

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action '{payload.action}'. Use 'save' or 'remove'.")
