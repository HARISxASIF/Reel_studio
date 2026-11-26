import uuid
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from app.main import app
from app.services.auth import get_current_user
from app.database import get_db
from app.models.user import User

mock_user = User(
    id=uuid.uuid4(),
    email="test@reelstudio.local",
    full_name="Test User",
    is_active=True,
)
app.dependency_overrides[get_current_user] = lambda: mock_user

async def mock_get_db():
    mock_session = MagicMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    async def mock_execute(*args, **kwargs):
        return mock_res
    mock_session.execute = mock_execute
    yield mock_session

app.dependency_overrides[get_db] = mock_get_db

client = TestClient(app)


def test_system_ai_status():
    response = client.get("/api/system/ai-status")
    assert response.status_code == 200
    data = response.json()
    assert "is_configured" in data
    assert "instructions" in data
    assert "model" in data


def test_url_metadata_ssrf_blocked():
    # Attempt SSRF to internal network
    response = client.post(
        "/api/projects/metadata",
        json={"url": "http://127.0.0.1:9000/bucket"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["can_import_media"] is False
    assert "Validation failed" in data["message"] or "restricted" in data["message"].lower() or "prohibited" in data["message"].lower()


def test_url_metadata_valid_platform():
    response = client.post(
        "/api/projects/metadata",
        json={"url": "https://www.youtube.com/watch?v=testvideo123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "youtube"


def test_validate_project_settings_split_screen():
    from app.routers.projects import validate_project_settings
    from fastapi import HTTPException

    # Valid split settings
    valid_fc = {"x": 0.7, "y": 0.05, "width": 0.25, "height": 0.35}
    valid_gp = {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
    validate_project_settings("split", 0.0, 54, valid_fc, valid_gp)

    # Missing crop
    with pytest.raises(HTTPException) as exc:
        validate_project_settings("split", 0.0, 54, None, valid_gp)
    assert exc.value.status_code == 400
    assert "Facecam crop region is required" in exc.value.detail

    # Out of bounds crop
    invalid_crop = {"x": 0.8, "y": 0.1, "width": 0.5, "height": 0.5}  # x + width = 1.3 > 1.0
    with pytest.raises(HTTPException) as exc:
        validate_project_settings("split", 0.0, 54, invalid_crop, valid_gp)
    assert exc.value.status_code == 400
    assert "stay within the source video bounds" in exc.value.detail

    # Invalid framing mode
    with pytest.raises(HTTPException) as exc:
        validate_project_settings("unknown_mode", 0.0, 54, None, None)
    assert exc.value.status_code == 400


def test_validate_project_settings_subtitles():
    from app.routers.projects import validate_project_settings
    from fastapi import HTTPException

    # Valid subtitle placement
    validate_project_settings(
        "crop", 0.0, 54, None, None,
        subtitle_position="middle",
        subtitle_y_percent=0.50,
        subtitle_color="#00FFFF",
        subtitle_font_family="Montserrat",
    )

    # Invalid subtitle position
    with pytest.raises(HTTPException) as exc:
        validate_project_settings(
            "crop", 0.0, 54, None, None,
            subtitle_position="invalid_pos",
        )
    assert exc.value.status_code == 400
    assert "Invalid subtitle position" in exc.value.detail

    # Out of range vertical offset
    with pytest.raises(HTTPException) as exc:
        validate_project_settings(
            "crop", 0.0, 54, None, None,
            subtitle_y_percent=0.99,
        )
    assert exc.value.status_code == 400
    assert "Subtitle vertical position must be between" in exc.value.detail


@pytest.mark.asyncio
async def test_delete_nonexistent_reel():
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        fake_id = uuid.uuid4()
        response = await ac.delete(f"/api/reels/{fake_id}")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_project():
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        fake_id = uuid.uuid4()
        response = await ac.delete(f"/api/projects/{fake_id}")
        assert response.status_code == 404


def test_youtube_oauth_authorize_url():
    response = client.get("/api/social/youtube/authorize?project_id=test-project-123")
    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "youtube"
    url = data["authorize_url"]
    assert "https://accounts.google.com/o/oauth2/v2/auth" in url
    assert "client_id=" in url
    assert "redirect_uri=" in url
    assert "scope=" in url
    assert "test-project-123" in url


def test_tiktok_prepare():
    with patch("app.routers.social.storage_service.generate_presigned_download_url", return_value="http://localhost:9000/test.mp4"):
        response = client.post(
            "/api/social/tiktok/prepare",
            params={
                "reel_id": str(uuid.uuid4()),
                "title": "Epic GTA 6 Moment",
                "description": "Watch this gameplay",
                "hashtags": "#gta6 #gaming",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "instructions" in data
        assert "tiktok_web_upload_url" in data
        assert "Epic GTA 6 Moment" in data["combined_text"]
        assert "#gta6" in data["combined_text"]



