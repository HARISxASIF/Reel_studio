import uuid
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.encryption import encrypt_token, decrypt_token
from app.services.gemini_limiter import GeminiRateLimiter


def test_encryption_roundtrip():
    """Verify Fernet encryption and decryption works reliably at rest."""
    sample_key = "AIzaSyD-dummy-test-key-12345678"
    enc = encrypt_token(sample_key)
    assert enc is not None
    assert enc != sample_key
    assert "AIza" not in enc

    dec = decrypt_token(enc)
    assert dec == sample_key


def test_scoped_gemini_limiter():
    """Verify rate limiter cooldowns are strictly scoped by user identifier."""
    limiter = GeminiRateLimiter()
    alice_id = "alice-user-123"
    bob_id = "bob-user-456"

    # Trigger cooldown for Alice
    limiter.record_rate_limit(cooldown_seconds=15, key_identifier=alice_id)

    # Alice should be blocked by cooldown
    allowed_alice, wait_alice, reason_alice = limiter.check_quota(key_identifier=alice_id)
    assert allowed_alice is False
    assert "rate_limit_cooldown" in reason_alice

    # Bob should NOT be blocked
    allowed_bob, wait_bob, reason_bob = limiter.check_quota(key_identifier=bob_id)
    assert allowed_bob is True
    assert reason_bob == "ok"


@pytest.mark.asyncio
async def test_multi_tenant_saas_lifecycle():
    """
    Unified end-to-end multi-tenant lifecycle test running inside a single event loop:
    1. Sign up, login, and verify persistent JWT sessions.
    2. Private workspaces: Alice creates projects; Bob sees an empty workspace and cannot access Alice's data.
    3. User-owned credentials: Encrypted storage, connection testing, and masked settings retrieval.
    """
    app.dependency_overrides.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        alice_email = f"alice_{uuid.uuid4().hex[:6]}@example.com"
        bob_email = f"bob_{uuid.uuid4().hex[:6]}@example.com"
        pwd = "password123"

        # --- PHASE 1: Sign up & Auth ---
        # Register Alice
        r_alice = await ac.post("/api/auth/signup", json={"email": alice_email, "password": pwd, "full_name": "Alice"})
        assert r_alice.status_code == 200
        alice_token = r_alice.json()["access_token"]
        alice_headers = {"Authorization": f"Bearer {alice_token}"}

        # Duplicate email rejected
        r_dup = await ac.post("/api/auth/signup", json={"email": alice_email, "password": pwd})
        assert r_dup.status_code == 400

        # Login Alice with JSON
        r_login = await ac.post("/api/auth/login/json", json={"email": alice_email, "password": pwd})
        assert r_login.status_code == 200

        # Register Bob
        r_bob = await ac.post("/api/auth/signup", json={"email": bob_email, "password": pwd, "full_name": "Bob"})
        assert r_bob.status_code == 200
        bob_token = r_bob.json()["access_token"]
        bob_headers = {"Authorization": f"Bearer {bob_token}"}

        # --- PHASE 2: Workspace Isolation ---
        # Both start with completely empty dashboards
        assert (await ac.get("/api/projects", headers=alice_headers)).json()["total"] == 0
        assert (await ac.get("/api/projects", headers=bob_headers)).json()["total"] == 0

        # Alice creates a project
        with patch("app.routers.projects.process_url_import.delay"):
            p_res = await ac.post(
                "/api/projects/url",
                json={"url": "https://www.youtube.com/watch?v=alicetest123", "title": "Alice Secret Video"},
                headers=alice_headers,
            )
            assert p_res.status_code == 200
            alice_project_id = p_res.json()["id"]

        # Alice sees her 1 project
        assert (await ac.get("/api/projects", headers=alice_headers)).json()["total"] == 1

        # Bob STILL sees 0 projects
        assert (await ac.get("/api/projects", headers=bob_headers)).json()["total"] == 0

        # Bob direct access attempts -> All MUST return 404 Not Found
        assert (await ac.get(f"/api/projects/{alice_project_id}", headers=bob_headers)).status_code == 404
        assert (await ac.patch(f"/api/projects/{alice_project_id}/settings", json={"framing_mode": "split"}, headers=bob_headers)).status_code == 404
        assert (await ac.delete(f"/api/projects/{alice_project_id}", headers=bob_headers)).status_code == 404
        assert (await ac.get(f"/api/projects/{alice_project_id}/sample-transcript", headers=bob_headers)).status_code == 404

        # --- PHASE 3: Settings & Integrations ---
        # Check initial integrations
        init_int = (await ac.get("/api/settings/integrations", headers=alice_headers)).json()
        assert init_int["gemini_configured"] is False
        assert init_int["youtube_configured"] is False
        assert "api/social/youtube/callback" in init_int["youtube_redirect_uri"]

        # Save Gemini API key (encrypted at rest)
        with patch("app.routers.settings._test_gemini_connectivity", return_value=("connected", "Test OK")):
            save_gem = await ac.post(
                "/api/settings/integrations/gemini",
                json={"action": "save", "api_key": "AIzaSyFakeKeyForTesting1234567890"},
                headers=alice_headers,
            )
            assert save_gem.status_code == 200

        # Check masked status
        gem_after = (await ac.get("/api/settings/integrations", headers=alice_headers)).json()
        assert gem_after["gemini_configured"] is True
        assert gem_after["gemini_status"] == "connected"
        assert "AIza" in gem_after["gemini_key_masked"]
        assert "••••" in gem_after["gemini_key_masked"]
        assert "FakeKeyForTesting" not in gem_after["gemini_key_masked"]

        # Bob's settings remain untouched (Bob hasn't configured Gemini yet)
        bob_int = (await ac.get("/api/settings/integrations", headers=bob_headers)).json()
        assert bob_int["gemini_configured"] is False

        # Save YouTube OAuth credentials
        save_yt = await ac.post(
            "/api/settings/integrations/youtube",
            json={
                "action": "save",
                "client_id": "alice-yt-client.apps.googleusercontent.com",
                "client_secret": "GOCSPX-SecretForTesting12345",
            },
            headers=alice_headers,
        )
        assert save_yt.status_code == 200

        yt_after = (await ac.get("/api/settings/integrations", headers=alice_headers)).json()
        assert yt_after["youtube_configured"] is True
        assert yt_after["youtube_client_id"] == "alice-yt-client.apps.googleusercontent.com"
        assert "GOCSPX" not in yt_after["youtube_secret_masked"]
        assert "••••" in yt_after["youtube_secret_masked"]
