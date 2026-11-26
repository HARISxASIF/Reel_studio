import uuid
import hashlib
import requests
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, RedirectResponse
from app.services.encryption import encrypt_token
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.models.social import SocialAccount, SocialPost
from app.schemas.social import (
    SocialAccountOut,
    ConnectMockAccountRequest,
    DisconnectAccountRequest,
    HashtagSuggestionRequest,
    HashtagSuggestionResponse,
    PublishBatchRequest,
    SocialPostOut,
    TikTokPrepareResponse,
)
from app.services.auth import get_current_user
from app.services.social_ai import suggest_hashtags
from app.services.social_publishers import format_combined_caption
from app.services.storage import storage_service
from app.tasks.social_tasks import publish_social_post_task
from app.config import settings

router = APIRouter(prefix="/api/social", tags=["social"])


@router.get("/accounts", response_model=List[SocialAccountOut])
async def list_social_accounts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all connected social accounts for the authenticated user."""
    query = (
        select(SocialAccount)
        .where(SocialAccount.user_id == current_user.id, SocialAccount.is_active == True)
        .order_by(SocialAccount.created_at.asc())
    )
    result = await db.execute(query)
    accounts = result.scalars().all()
    return accounts


@router.post("/accounts/mock", response_model=SocialAccountOut)
async def connect_mock_account(
    req: ConnectMockAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Connect a mock/test account for safe local testing and development.
    Supports YouTube, Facebook, Instagram, and TikTok.
    """
    platform = req.platform.lower().strip()
    if platform not in ["youtube", "facebook", "instagram", "tiktok"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported platform '{platform}'. Choose youtube, facebook, instagram, or tiktok.",
        )

    # Check if existing mock account for this platform exists
    query = select(SocialAccount).where(
        SocialAccount.user_id == current_user.id,
        SocialAccount.platform == platform,
        SocialAccount.is_mock == True,
    )
    res = await db.execute(query)
    existing = res.scalars().first()

    default_avatars = {
        "youtube": "https://www.youtube.com/s/desktop/f6b0f342/img/favicon_144x144.png",
        "facebook": "https://static.xx.fbcdn.net/rsrc.php/yb/r/4DxpaE-S59P.ico",
        "instagram": "https://static.cdninstagram.com/rsrc.php/v3/yI/r/VsNE-OHk_8a.png",
        "tiktok": "https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/images/logo.png",
    }

    if existing:
        existing.account_name = req.account_name
        existing.account_username = req.account_username or existing.account_username
        existing.profile_picture_url = req.profile_picture_url or existing.profile_picture_url or default_avatars.get(platform)
        existing.status = "connected"
        existing.is_active = True
        existing.metadata_json = req.metadata_json or existing.metadata_json
        await db.commit()
        await db.refresh(existing)
        return existing

    mock_account = SocialAccount(
        user_id=current_user.id,
        platform=platform,
        platform_account_id=f"mock_{platform}_{uuid.uuid4().hex[:8]}",
        account_name=req.account_name,
        account_username=req.account_username or f"@{req.account_name.lower().replace(' ', '_')}",
        profile_picture_url=req.profile_picture_url or default_avatars.get(platform),
        status="connected",
        is_active=True,
        is_mock=True,
        metadata_json=req.metadata_json or {"simulation_mode": True},
    )
    db.add(mock_account)
    await db.commit()
    await db.refresh(mock_account)
    return mock_account


@router.post("/accounts/disconnect", response_model=dict)
async def disconnect_account(
    req: DisconnectAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Disconnect a social account and cancel any pending queued posts for it.
    """
    query = select(SocialAccount).where(
        SocialAccount.id == req.account_id,
        SocialAccount.user_id == current_user.id,
    )
    res = await db.execute(query)
    account = res.scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    account.status = "disconnected"
    account.is_active = False

    # Stop pending queued posts for this account
    queued_posts_query = select(SocialPost).where(
        SocialPost.social_account_id == account.id,
        SocialPost.status == "queued",
    )
    p_res = await db.execute(queued_posts_query)
    for p in p_res.scalars().all():
        p.status = "failed"
        p.error_message = "Post cancelled: Destination account was disconnected before upload."

    await db.commit()
    return {"status": "disconnected", "account_id": str(account.id)}


@router.post("/accounts/reconnect", response_model=SocialAccountOut)
async def reconnect_account(
    req: DisconnectAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reconnect or re-activate a disconnected social account."""
    query = select(SocialAccount).where(
        SocialAccount.id == req.account_id,
        SocialAccount.user_id == current_user.id,
    )
    res = await db.execute(query)
    account = res.scalars().first()
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    account.status = "connected"
    account.is_active = True
    await db.commit()
    await db.refresh(account)
    return account


@router.post("/hashtags/suggest", response_model=HashtagSuggestionResponse)
async def suggest_reel_hashtags(
    req: HashtagSuggestionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Suggest contextual AI hashtags via Gemini based on reel title, description, and transcript snippet.
    """
    # Look up reel verifying ownership through project
    reel_res = await db.execute(
        select(Reel).join(Project, Reel.project_id == Project.id).where(
            Reel.id == req.reel_id, Project.user_id == current_user.id
        )
    )
    reel = reel_res.scalars().first()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    transcript_text = ""
    if reel and reel.transcript_words:
        words = [w.get("word", "") for w in reel.transcript_words if isinstance(w, dict)]
        transcript_text = " ".join(words)

    result = suggest_hashtags(
        reel_id=str(req.reel_id),
        title=req.title,
        description=req.description,
        transcript_text=transcript_text,
        brand_tags=req.brand_tags,
    )

    return HashtagSuggestionResponse(
        reel_id=req.reel_id,
        suggestions=result.get("suggestions", []),
        context_keywords=result.get("context_keywords", []),
        cached=result.get("cached", False),
    )


@router.post("/publish/batch", response_model=List[SocialPostOut])
async def publish_batch(
    req: PublishBatchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Queue approved reels to selected destination accounts in background Celery workers.
    Performs snapshotting of video key and metadata, and prevents duplicate submissions.
    """
    if not req.items:
        raise HTTPException(status_code=400, detail="No publish items provided")

    # Verify project
    p_res = await db.execute(select(Project).where(Project.id == req.project_id, Project.user_id == current_user.id))
    project = p_res.scalars().first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    created_posts: List[SocialPost] = []

    for item in req.items:
        # Verify reel
        r_res = await db.execute(select(Reel).where(Reel.id == item.reel_id, Reel.project_id == req.project_id))
        reel = r_res.scalars().first()
        if not reel:
            continue

        if not reel.video_key:
            raise HTTPException(status_code=400, detail=f"Reel '{reel.top_caption}' has not finished video rendering yet.")

        combined_caption = format_combined_caption(
            title=item.post_title,
            description=item.post_description,
            hashtags=item.post_hashtags,
        )

        for account_id in item.account_ids:
            # Verify account
            a_res = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.id == account_id,
                    SocialAccount.user_id == current_user.id,
                    SocialAccount.is_active == True,
                )
            )
            account = a_res.scalars().first()
            if not account or account.status == "disconnected":
                continue

            # Deterministic idempotency key
            idempotency_raw = f"{reel.id}:{account.id}:{item.post_title.strip()}"
            idempotency_key = hashlib.sha256(idempotency_raw.encode("utf-8")).hexdigest()

            # Check if active post already exists
            existing_res = await db.execute(
                select(SocialPost).where(SocialPost.idempotency_key == idempotency_key)
            )
            existing_post = existing_res.scalars().first()

            if existing_post and existing_post.status in ("queued", "uploading", "published"):
                created_posts.append(existing_post)
                continue

            # Create post snapshot
            post = SocialPost(
                project_id=req.project_id,
                reel_id=reel.id,
                social_account_id=account.id,
                user_id=current_user.id,
                platform=account.platform,
                post_title=item.post_title,
                post_description=item.post_description,
                post_hashtags=item.post_hashtags,
                combined_caption=combined_caption,
                platform_options=item.platform_options or {},
                video_key_snapshot=reel.video_key,
                rendered_video_url=storage_service.generate_presigned_download_url(reel.video_key) if reel.video_key else None,
                status="queued",
                progress=0,
                idempotency_key=idempotency_key,
            )
            db.add(post)
            await db.flush()  # assign UUID

            # Dispatch background worker task
            try:
                publish_social_post_task.delay(str(post.id))
            except Exception as ce:
                # In case Celery or Redis is unreachable in tests, don't crash
                post.error_message = f"Queueing error: {ce}"

            created_posts.append(post)

    await db.commit()

    # Format responses with account details
    out_list = []
    for cp in created_posts:
        await db.refresh(cp)
        acc_res = await db.execute(select(SocialAccount).where(SocialAccount.id == cp.social_account_id))
        acc = acc_res.scalars().first()
        out = SocialPostOut.model_validate(cp)
        if acc:
            out.account_name = acc.account_name
            out.account_username = acc.account_username
        out_list.append(out)

    return out_list


@router.get("/posts/project/{project_id}", response_model=List[SocialPostOut])
async def list_project_social_posts(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all social publishing posts for a project."""
    query = (
        select(SocialPost)
        .where(SocialPost.project_id == project_id, SocialPost.user_id == current_user.id)
        .order_by(desc(SocialPost.created_at))
    )
    res = await db.execute(query)
    posts = res.scalars().all()

    out_list = []
    for p in posts:
        out = SocialPostOut.model_validate(p)
        acc_res = await db.execute(select(SocialAccount).where(SocialAccount.id == p.social_account_id))
        acc = acc_res.scalars().first()
        if acc:
            out.account_name = acc.account_name
            out.account_username = acc.account_username
        out_list.append(out)

    return out_list


@router.post("/posts/{post_id}/retry", response_model=SocialPostOut)
async def retry_failed_post(
    post_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retry a failed or stalled publishing post."""
    query = select(SocialPost).where(SocialPost.id == post_id, SocialPost.user_id == current_user.id)
    res = await db.execute(query)
    post = res.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Social post not found")

    post.status = "queued"
    post.progress = 0
    post.error_message = None
    post.retry_count = (post.retry_count or 0) + 1
    await db.commit()
    await db.refresh(post)

    try:
        publish_social_post_task.delay(str(post.id))
    except Exception as ce:
        post.error_message = f"Retry queueing error: {ce}"
        await db.commit()

    out = SocialPostOut.model_validate(post)
    acc_res = await db.execute(select(SocialAccount).where(SocialAccount.id == post.social_account_id))
    acc = acc_res.scalars().first()
    if acc:
        out.account_name = acc.account_name
        out.account_username = acc.account_username
    return out


@router.post("/tiktok/prepare", response_model=TikTokPrepareResponse)
async def prepare_for_tiktok(
    reel_id: uuid.UUID,
    title: str = Query(...),
    description: Optional[str] = Query(None),
    hashtags: Optional[str] = Query(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Prepare reel for manual TikTok upload:
    Generates download link for rendered MP4, packages formatted caption and hashtags,
    and returns a direct link to open TikTok upload.
    """
    r_res = await db.execute(
        select(Reel).join(Project, Reel.project_id == Project.id).where(
            Reel.id == reel_id, Project.user_id == current_user.id
        )
    )
    reel = r_res.scalars().first()
    if not reel:
        raise HTTPException(status_code=404, detail="Reel not found")

    if not reel.video_key:
        raise HTTPException(status_code=400, detail="Reel has not finished video rendering yet.")

    download_url = storage_service.generate_presigned_download_url(
        file_key=reel.video_key,
        expires_in=7200,
        filename=f"reel_{reel_id}.mp4",
    )

    tag_list = [t.strip() for t in (hashtags or "").split(",") if t.strip()]
    combined_caption = format_combined_caption(
        title=title,
        description=description,
        hashtags=tag_list,
        max_length=2200,
    )

    return TikTokPrepareResponse(
        reel_id=reel_id,
        download_url=download_url,
        caption=combined_caption,
        hashtags=tag_list,
        combined_text=combined_caption,
        tiktok_web_upload_url="https://www.tiktok.com/upload",
        instructions="1. Click Download Video to save your MP4. 2. Click Copy Caption & Tags. 3. Click Open TikTok Upload and paste your text.",
    )


# Official OAuth URL generation & callback endpoints
@router.get("/{platform}/authorize")
async def get_oauth_authorize_url(
    platform: str,
    project_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate official OAuth authorization URL for the requested platform using user-owned credentials."""
    plat = platform.lower()
    from app.services.oauth_state import create_oauth_state

    if plat == "youtube":
        from app.models.user_credential import UserCredential
        c_res = await db.execute(select(UserCredential).where(UserCredential.user_id == current_user.id))
        creds = c_res.scalar_one_or_none()

        client_id = (creds and creds.youtube_client_id) or settings.YOUTUBE_CLIENT_ID
        if not client_id:
            raise HTTPException(
                status_code=400,
                detail="YouTube OAuth Client ID and Secret are not configured. Please open Settings → Integrations → YouTube to add your Google Cloud credentials.",
            )

        redirect_uri = settings.YOUTUBE_REDIRECT_URI or f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/social/youtube/callback"
        state = create_oauth_state(
            user_id=current_user.id,
            platform="youtube",
            client_id=client_id,
            project_id=project_id,
        )

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
        return {"authorize_url": url, "platform": plat}

    elif plat in ("facebook", "instagram"):
        app_id = settings.META_APP_ID
        if not app_id:
            raise HTTPException(
                status_code=400,
                detail="Meta App ID is not configured in .env. Enter META_APP_ID or use Mock Connect for testing.",
            )
        state = create_oauth_state(user_id=current_user.id, platform=plat, project_id=project_id)
        params = {
            "client_id": app_id,
            "redirect_uri": settings.META_REDIRECT_URI,
            "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,instagram_basic,instagram_content_publish",
            "state": state,
        }
        url = f"https://www.facebook.com/v19.0/dialog/oauth?{urllib.parse.urlencode(params)}"
        return {"authorize_url": url, "platform": plat}

    elif plat == "tiktok":
        client_key = settings.TIKTOK_CLIENT_KEY
        if not client_key:
            raise HTTPException(
                status_code=400,
                detail="TikTok Client Key is not configured in .env. Enter TIKTOK_CLIENT_KEY or use Mock Connect / Manual Prepare.",
            )
        state = create_oauth_state(user_id=current_user.id, platform=plat, project_id=project_id)
        params = {
            "client_key": client_key,
            "scope": "user.info.basic,video.upload,video.publish",
            "response_type": "code",
            "redirect_uri": settings.TIKTOK_REDIRECT_URI,
            "state": state,
        }
        url = f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"
        return {"authorize_url": url, "platform": plat}

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported platform '{plat}'")


@router.get("/youtube/callback", response_class=HTMLResponse)
async def youtube_oauth_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Google OAuth callback using user's configured Client ID & Secret.
    Validates and consumes single-use state, exchanges code for tokens,
    fetches YouTube channel profile, and stores encrypted tokens.
    """
    from app.services.oauth_state import consume_oauth_state
    from app.models.user_credential import UserCredential
    from app.services.encryption import decrypt_token

    state_data = consume_oauth_state(state) if state else None

    # Fallback to legacy state parsing if migration is in flight
    if not state_data and state and ":" in state:
        parts = state.split(":")
        if len(parts) >= 3:
            state_data = {"user_id": parts[0], "project_id": parts[2] if parts[2] != "default" else None}

    user_id_str = state_data.get("user_id") if state_data else None
    project_id_str = state_data.get("project_id") if state_data else None
    target_redirect = (
        f"{settings.FRONTEND_PUBLIC_URL}/projects/{project_id_str}"
        if project_id_str and project_id_str != "default"
        else f"{settings.FRONTEND_PUBLIC_URL}/settings"
    )

    if not state_data or not user_id_str:
        return HTMLResponse(
            content=f"""
            <div style="background:#0f172a; color:#fff; font-family:sans-serif; padding:40px; text-align:center;">
              <h3 style="color:#ef4444;">Authorization Session Expired or Invalid</h3>
              <p style="color:#94a3b8;">This connection link has expired or has already been used. Please return to Reel Studio and try connecting again.</p>
              <a href="{target_redirect}" style="display:inline-block; margin-top:16px; background:#4f46e5; color:#fff; text-decoration:none; padding:10px 20px; border-radius:8px;">Return to Reel Studio</a>
            </div>
            """,
            status_code=400,
        )

    if error or not code:
        err_msg = error or "No authorization code received from Google."
        troubleshoot_tip = ""
        if "access_denied" in str(error).lower():
            troubleshoot_tip = "Google rejected access. If your Google Cloud project is in 'Testing' mode, make sure your channel's Google account is listed under Test Users in Google Auth Platform branding."

        return HTMLResponse(
            content=f"""
            <div style="background:#0f172a; color:#fff; font-family:sans-serif; padding:40px; text-align:center;">
              <h3 style="color:#ef4444;">YouTube Authorization Failed</h3>
              <p style="color:#94a3b8;">{err_msg}</p>
              {f'<p style="color:#fbbf24; font-size:13px; max-width:500px; margin:16px auto;"><strong>Troubleshooting Tip:</strong> {troubleshoot_tip}</p>' if troubleshoot_tip else ''}
              <a href="{target_redirect}" style="display:inline-block; margin-top:16px; background:#4f46e5; color:#fff; text-decoration:none; padding:10px 20px; border-radius:8px;">Return to Reel Studio</a>
            </div>
            """,
            status_code=400,
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except Exception:
        return HTMLResponse(content="<h3>Invalid user ID in state token</h3>", status_code=400)

    # Resolve user's OAuth Client ID and Client Secret
    c_res = await db.execute(select(UserCredential).where(UserCredential.user_id == user_uuid))
    user_cred = c_res.scalar_one_or_none()

    client_id = (user_cred and user_cred.youtube_client_id) or settings.YOUTUBE_CLIENT_ID
    client_secret = None
    if user_cred and user_cred.youtube_client_secret_encrypted:
        try:
            client_secret = decrypt_token(user_cred.youtube_client_secret_encrypted)
        except Exception:
            pass
    if not client_secret:
        client_secret = settings.YOUTUBE_CLIENT_SECRET

    if not client_id or not client_secret:
        return HTMLResponse(
            content="<h3>YouTube OAuth Client ID or Client Secret not found for user. Please save your credentials in Settings.</h3>",
            status_code=400,
        )

    redirect_uri = settings.YOUTUBE_REDIRECT_URI or f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/social/youtube/callback"
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    res = requests.post(token_url, data=data, timeout=30)
    if res.status_code != 200:
        res_json = {}
        try:
            res_json = res.json()
        except Exception:
            pass
        err_desc = res_json.get("error_description", res.text)
        tip = ""
        if "redirect_uri_mismatch" in str(err_desc).lower():
            tip = f"The Authorized redirect URI in Google Cloud Console must match exactly: <code>{redirect_uri}</code>"
        elif "unauthorized_client" in str(err_desc).lower():
            tip = "The Client Secret does not match the Client ID entered. Please recheck your credentials in Settings."

        return HTMLResponse(
            content=f"""
            <div style="background:#0f172a; color:#fff; font-family:sans-serif; padding:40px; text-align:center;">
              <h3 style="color:#ef4444;">Token Exchange Failed</h3>
              <p style="color:#94a3b8;">{err_desc}</p>
              {f'<p style="color:#fbbf24; font-size:13px; max-width:500px; margin:16px auto;"><strong>Fix:</strong> {tip}</p>' if tip else ''}
              <a href="{target_redirect}" style="display:inline-block; margin-top:16px; background:#4f46e5; color:#fff; text-decoration:none; padding:10px 20px; border-radius:8px;">Return to Settings</a>
            </div>
            """,
            status_code=400,
        )

    token_data = res.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 3600)
    token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # Query YouTube channel details
    channel_name = "My YouTube Channel"
    channel_user = None
    channel_id = f"yt_{uuid.uuid4().hex[:8]}"
    avatar_url = None

    try:
        ch_res = requests.get(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        if ch_res.status_code == 200:
            ch_data = ch_res.json()
            items = ch_data.get("items", [])
            if items:
                channel_id = items[0].get("id", channel_id)
                snippet = items[0].get("snippet", {})
                channel_name = snippet.get("title", channel_name)
                channel_user = snippet.get("customUrl")
                thumbs = snippet.get("thumbnails", {})
                avatar_url = thumbs.get("default", {}).get("url")
    except Exception:
        pass

    # Upsert into social_accounts
    q = select(SocialAccount).where(
        SocialAccount.user_id == user_uuid,
        SocialAccount.platform == "youtube",
    )
    existing_res = await db.execute(q)
    account = existing_res.scalars().first()

    if account:
        account.platform_account_id = channel_id
        account.account_name = channel_name
        account.account_username = channel_user or account.account_username
        account.profile_picture_url = avatar_url or account.profile_picture_url
        account.access_token_encrypted = encrypt_token(access_token)
        if refresh_token:
            account.refresh_token_encrypted = encrypt_token(refresh_token)
        account.token_expires_at = token_expires_at
        account.status = "connected"
        account.is_active = True
        account.is_mock = False
        meta = account.metadata_json or {}
        meta["oauth_client_id"] = client_id
        account.metadata_json = meta
    else:
        account = SocialAccount(
            user_id=user_uuid,
            platform="youtube",
            platform_account_id=channel_id,
            account_name=channel_name,
            account_username=channel_user,
            profile_picture_url=avatar_url,
            access_token_encrypted=encrypt_token(access_token),
            refresh_token_encrypted=encrypt_token(refresh_token) if refresh_token else None,
            token_expires_at=token_expires_at,
            metadata_json={"oauth_client_id": client_id},
            status="connected",
            is_active=True,
            is_mock=False,
        )
        db.add(account)

    await db.commit()

    return HTMLResponse(
        content=f"""
        <!DOCTYPE html>
        <html>
          <head>
            <title>YouTube Connected</title>
            <meta http-equiv="refresh" content="2;url={target_redirect}" />
          </head>
          <body style="background:#0f172a; color:#fff; font-family:system-ui, -apple-system, sans-serif; display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; margin:0;">
            <div style="background:#1e293b; padding:32px; border-radius:16px; border:1px solid #334155; text-align:center; max-width:420px; box-shadow:0 20px 25px -5px rgba(0,0,0,0.5);">
              <div style="font-size:36px; margin-bottom:12px;">🎉</div>
              <h2 style="color:#10b981; margin:0 0 8px 0; font-size:20px;">Successfully Connected!</h2>
              <p style="color:#e2e8f0; font-size:14px; margin:0 0 16px 0;"><strong>{channel_name}</strong> is now connected to Reel Studio.</p>
              <p style="color:#94a3b8; font-size:12px; margin:0 0 16px 0;">Redirecting you back to your project...</p>
              <a href="{target_redirect}" style="display:inline-block; background:#4f46e5; color:#fff; text-decoration:none; padding:10px 20px; border-radius:8px; font-size:13px; font-weight:bold;">Return to Reel Studio</a>
            </div>
          </body>
        </html>
        """
    )
