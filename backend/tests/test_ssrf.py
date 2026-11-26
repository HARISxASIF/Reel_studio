import pytest
from app.services.url_importer import validate_url_security, is_ip_allowed, detect_platform


def test_ip_blocking():
    # Private & loopback IPs must be blocked
    assert is_ip_allowed("127.0.0.1") is False
    assert is_ip_allowed("10.0.0.1") is False
    assert is_ip_allowed("192.168.1.1") is False
    assert is_ip_allowed("172.16.0.1") is False
    assert is_ip_allowed("169.254.169.254") is False
    assert is_ip_allowed("::1") is False

    # Public IPs must be allowed
    assert is_ip_allowed("8.8.8.8") is True
    assert is_ip_allowed("1.1.1.1") is True


def test_url_security_disallowed_schemes():
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_url_security("file:///etc/passwd")

    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        validate_url_security("ftp://example.com/video.mp4")


def test_url_security_local_hosts():
    with pytest.raises(ValueError, match="Access to local network hosts is strictly prohibited"):
        validate_url_security("http://localhost:8000/api")

    with pytest.raises(ValueError, match="Access to local network hosts is strictly prohibited"):
        validate_url_security("http://127.0.0.1:9000/bucket")


def test_platform_detection():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert detect_platform("https://www.twitch.tv/videos/123456789") == "twitch"
    assert detect_platform("https://kick.com/video/abc-123") == "kick"
    assert detect_platform("https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4") == "direct_url"
