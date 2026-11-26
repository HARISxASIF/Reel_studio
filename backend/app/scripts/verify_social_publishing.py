import uuid
import sys
import logging
from app.database import SyncSessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.reel import Reel
from app.models.social import SocialAccount, SocialPost
from app.services.encryption import encrypt_token, decrypt_token
from app.services.social_ai import suggest_hashtags
from app.services.social_publishers import format_combined_caption
from app.tasks.social_tasks import publish_social_post_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_social")


def run_verification():
    print("=" * 70)
    print("STARTING SOCIAL MEDIA PUBLISHING END-TO-END VERIFICATION")
    print("=" * 70)

    db = SyncSessionLocal()
    try:
        # Step 1: Token Encryption & Decryption
        print("\n[Step 1/6] Testing Fernet Token Encryption & Decryption...")
        secret_sample = "ya29.a0AfH6SMB_sample_oauth_token_secret_12345"
        encrypted = encrypt_token(secret_sample)
        decrypted = decrypt_token(encrypted)
        assert encrypted != secret_sample, "Token was not encrypted"
        assert decrypted == secret_sample, "Decrypted token does not match original"
        print("  ✓ Encryption and decryption verified with Fernet key.")

        # Step 2: AI Hashtag Suggestions & Caching
        print("\n[Step 2/6] Testing AI Hashtag Suggestion & Brand Tags...")
        test_reel_id = str(uuid.uuid4())
        res = suggest_hashtags(
            reel_id=test_reel_id,
            title="EXPLORING VICE CITY SECRET EASTER EGGS IN GTA 6",
            description="Insane hidden details found in Vice City waterfront",
            transcript_text="Look at that building over there, that is the exact club from the original Vice City!",
            brand_tags=["#ReelStudioGamer", "#OfficialGTA"],
        )
        assert len(res["suggestions"]) >= 5, "Expected at least 5 hashtag suggestions"
        assert "#ReelStudioGamer" in res["suggestions"], "Brand tag missing"
        assert res["cached"] is False, "Initial run should not be cached"

        # Test cache
        cached_res = suggest_hashtags(
            reel_id=test_reel_id,
            title="EXPLORING VICE CITY SECRET EASTER EGGS IN GTA 6",
        )
        assert cached_res["cached"] is True, "Second lookup should hit cache"
        print(f"  ✓ AI Hashtags verified ({len(res['suggestions'])} tags generated, caching active).")
        print(f"    Sample tags: {', '.join(res['suggestions'][:6])}")

        # Step 3: Social Account Connection & Disconnect protection
        print("\n[Step 3/6] Testing Account Management & Disconnect Safeguards...")
        user = db.query(User).first()
        if not user:
            print("  ! No user found in DB, skipping DB account tests")
            return

        # Create or update mock accounts for YouTube and Instagram
        yt_acc = db.query(SocialAccount).filter(
            SocialAccount.user_id == user.id,
            SocialAccount.platform == "youtube",
            SocialAccount.is_mock == True,
        ).first()

        if not yt_acc:
            yt_acc = SocialAccount(
                user_id=user.id,
                platform="youtube",
                platform_account_id="mock_yt_test_channel",
                account_name="GTA Highlights Central",
                account_username="@gta_clips",
                status="connected",
                is_active=True,
                is_mock=True,
            )
            db.add(yt_acc)
            db.commit()
            db.refresh(yt_acc)
        else:
            yt_acc.status = "connected"
            yt_acc.is_active = True
            db.commit()

        ig_acc = db.query(SocialAccount).filter(
            SocialAccount.user_id == user.id,
            SocialAccount.platform == "instagram",
            SocialAccount.is_mock == True,
        ).first()

        if not ig_acc:
            ig_acc = SocialAccount(
                user_id=user.id,
                platform="instagram",
                platform_account_id="mock_ig_test_account",
                account_name="Reel Studio Gaming",
                account_username="@reelstudio_gaming",
                status="connected",
                is_active=True,
                is_mock=True,
            )
            db.add(ig_acc)
            db.commit()
            db.refresh(ig_acc)
        else:
            ig_acc.status = "connected"
            ig_acc.is_active = True
            db.commit()

        print(f"  ✓ Connected Test Accounts verified (YouTube: {yt_acc.account_name}, IG: {ig_acc.account_name}).")

        # Step 4: Batch Publishing Simulation with Completed Reels
        print("\n[Step 4/6] Testing Multi-Reel Publishing & Snapshot Integrity...")
        project = db.query(Project).filter(Project.title.ilike("%VICE CITY%")).first()
        if not project:
            project = db.query(Project).first()

        completed_reels = db.query(Reel).filter(
            Reel.project_id == project.id,
            Reel.render_status == "completed",
            Reel.video_key != None,
        ).limit(2).all()

        assert len(completed_reels) > 0, "No completed reels found to test publish"
        print(f"  Found {len(completed_reels)} completed export reels in project '{project.title}'.")

        created_post_ids = []
        for reel in completed_reels:
            post_caption = format_combined_caption(
                title=reel.top_caption,
                description=reel.reason,
                hashtags=["#GTA6", "#GamingReels", "#Shorts"],
            )

            post = SocialPost(
                project_id=project.id,
                reel_id=reel.id,
                social_account_id=yt_acc.id,
                user_id=user.id,
                platform=yt_acc.platform,
                post_title=reel.top_caption,
                post_description=reel.reason,
                post_hashtags=["#GTA6", "#GamingReels", "#Shorts"],
                combined_caption=post_caption,
                video_key_snapshot=reel.video_key,
                rendered_video_url=f"http://localhost:9000/reel-studio/{reel.video_key}",
                status="queued",
                progress=0,
                idempotency_key=f"test:{reel.id}:{yt_acc.id}:{uuid.uuid4().hex[:6]}",
            )
            db.add(post)
            db.commit()
            db.refresh(post)
            created_post_ids.append(post.id)

        print(f"  ✓ Created {len(created_post_ids)} queued social post records with video snapshots.")

        # Step 5: Worker Execution & State Verification
        print("\n[Step 5/6] Executing Background Worker Publishing Tasks...")
        for p_id in created_post_ids:
            # Execute worker task synchronously to verify full pipeline
            publish_social_post_task(str(p_id))

            # Reload post from DB with fresh transaction state
            db.expire_all()
            updated_post = db.query(SocialPost).filter(SocialPost.id == p_id).first()
            assert updated_post.status == "published", f"Post status should be published, got {updated_post.status}"
            assert updated_post.progress == 100, f"Post progress should be 100, got {updated_post.progress}"
            assert updated_post.provider_post_url is not None, "Post URL should be populated"
            print(f"  ✓ Post {updated_post.id} ({updated_post.platform}): Status={updated_post.status}, URL={updated_post.provider_post_url}")

        # Step 6: Disconnect Protection & Stop Queued Posts Test
        print("\n[Step 6/6] Verifying Disconnect Protection & Queue Stopping...")
        dummy_post = SocialPost(
            project_id=project.id,
            reel_id=completed_reels[0].id,
            social_account_id=yt_acc.id,
            user_id=user.id,
            platform=yt_acc.platform,
            post_title="Dummy Post on Disconnected Account",
            status="queued",
            idempotency_key=f"disconnect_test_{uuid.uuid4().hex[:8]}",
        )
        db.add(dummy_post)
        db.commit()
        db.refresh(dummy_post)

        # Mark account disconnected
        yt_acc.status = "disconnected"
        yt_acc.is_active = False
        db.commit()

        # Run task on dummy post
        publish_social_post_task(str(dummy_post.id))
        db.expire_all()
        db.refresh(dummy_post)
        assert dummy_post.status in ("reconnect_required", "failed"), f"Expected stopped post status, got {dummy_post.status}"
        print(f"  ✓ Disconnected account prevented publication: Status={dummy_post.status}, Error='{dummy_post.error_message}'")

        # Restore account status
        yt_acc.status = "connected"
        yt_acc.is_active = True
        db.commit()

        print("\n" + "=" * 70)
        print("ALL SOCIAL MEDIA PUBLISHING VERIFICATIONS PASSED SUCCESSFULLY!")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    run_verification()
