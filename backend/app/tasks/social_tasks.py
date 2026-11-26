import uuid
import logging
from datetime import datetime
from app.tasks.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models.social import SocialAccount, SocialPost
from app.models.reel import Reel
from app.services.social_publishers import publish_post_to_destination, PublishingError

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2)
def publish_social_post_task(self, post_id_str: str):
    """
    Background worker task to publish a single queued reel to its assigned social destination.
    Provides snapshot stability, token validation, progress tracking, and idempotent deduplication.
    """
    post_id = uuid.UUID(post_id_str)
    db = SyncSessionLocal()

    try:
        post = db.query(SocialPost).filter(SocialPost.id == post_id).first()
        if not post:
            logger.warning(f"SocialPost {post_id} not found in database.")
            return

        # Idempotency check: prevent duplicate submission
        if post.status == "published":
            logger.info(f"SocialPost {post_id} is already published ({post.provider_post_url}). Skipping.")
            return

        account = db.query(SocialAccount).filter(SocialAccount.id == post.social_account_id).first()
        if not account or account.status == "disconnected" or not account.is_active:
            post.status = "reconnect_required"
            post.error_message = "Destination social account is disconnected or invalid. Reconnection required."
            db.commit()
            return

        reel = db.query(Reel).filter(Reel.id == post.reel_id).first()
        if not reel:
            post.status = "failed"
            post.error_message = "Source reel not found."
            db.commit()
            return

        # Mark as uploading
        post.status = "uploading"
        post.progress = 10
        post.error_message = None
        db.commit()

        def progress_callback(progress_pct: int, status_name: str = "uploading"):
            try:
                post.progress = max(post.progress, progress_pct)
                post.status = status_name
                db.commit()
            except Exception as pe:
                logger.warning(f"Error updating progress callback for post {post_id}: {pe}")

        # Execute platform publisher
        result = publish_post_to_destination(
            account=account,
            post=post,
            reel=reel,
            progress_callback=progress_callback,
        )

        # Mark published
        post.status = "published"
        post.progress = 100
        post.published_at = datetime.utcnow()
        post.provider_post_id = str(result.get("provider_post_id", ""))
        post.provider_post_url = str(result.get("provider_post_url", ""))
        post.provider_upload_id = str(result.get("provider_upload_id", ""))
        post.error_message = None
        db.commit()
        logger.info(f"Successfully published post {post_id} to {account.platform}: {post.provider_post_url}")

    except PublishingError as pe:
        logger.warning(f"PublishingError for post {post_id} ({account.platform if 'account' in locals() else 'unknown'}): {pe.message}")
        if 'post' in locals() and post:
            if pe.requires_reconnect:
                post.status = "reconnect_required"
                if 'account' in locals() and account:
                    account.status = "reconnect_required"
            else:
                post.status = "failed"
            post.error_message = pe.message
            db.commit()

        if pe.is_retryable and self.request.retries < self.max_retries:
            post.retry_count = self.request.retries + 1
            db.commit()
            raise self.retry(exc=pe, countdown=15)

    except Exception as e:
        logger.exception(f"Unexpected error publishing post {post_id}: {e}")
        if 'post' in locals() and post:
            post.status = "failed"
            post.error_message = f"Publishing failed: {str(e)}"
            db.commit()

    finally:
        db.close()
