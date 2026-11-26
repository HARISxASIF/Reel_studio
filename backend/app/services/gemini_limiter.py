import time
import logging
from typing import Tuple, Dict, Any, Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Fallback in-memory tracking if Redis is unreachable
_fallback_rpm: Dict[int, int] = {}
_fallback_tpm: Dict[int, int] = {}
_fallback_rpd: Dict[str, int] = {}
_fallback_cooldown_until: float = 0.0


def _get_redis_client() -> Optional[redis.Redis]:
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception as e:
        logger.debug(f"Redis unavailable for gemini_limiter: {e}")
        return None


class GeminiRateLimiter:
    """
    Distributed Redis-backed rate limiter for Gemini API across all jobs (live + uploaded).
    Enforces RPM, TPM, RPD, and dynamic 429 cooldowns.
    """

    def __init__(self):
        self.rpm_limit = settings.GEMINI_RPM
        self.tpm_limit = settings.GEMINI_TPM
        self.rpd_limit = settings.GEMINI_RPD
        self.default_cooldown = settings.GEMINI_RETRY_COOLDOWN_SECONDS

    def _get_prefix(self, key_identifier: Optional[str] = None) -> str:
        if key_identifier:
            # Clean identifier for redis key
            clean_id = "".join(c for c in str(key_identifier) if c.isalnum() or c in ("-", "_"))
            return f"gemini:limiter:{clean_id}"
        return "gemini:limiter:global"

    def check_quota(self, estimated_tokens: int = 2000, key_identifier: Optional[str] = None) -> Tuple[bool, float, str]:
        """
        Check if a Gemini call is allowed right now for this user / key.
        Returns:
            (is_allowed: bool, wait_seconds: float, reason: str)
        """
        now = time.time()
        minute_bucket = int(now // 60)
        day_bucket = time.strftime("%Y-%m-%d", time.gmtime(now))
        seconds_left_in_minute = max(1.0, 60.0 - (now % 60))
        pfx = self._get_prefix(key_identifier)

        client = _get_redis_client()
        if client:
            try:
                # 1. Check Cooldown
                cooldown_ttl = client.ttl(f"{pfx}:cooldown")
                if cooldown_ttl and cooldown_ttl > 0:
                    return False, float(cooldown_ttl), f"rate_limit_cooldown ({cooldown_ttl}s remaining)"

                pipe = client.pipeline()
                pipe.get(f"{pfx}:rpm:{minute_bucket}")
                pipe.get(f"{pfx}:tpm:{minute_bucket}")
                pipe.get(f"{pfx}:rpd:{day_bucket}")
                rpm_val, tpm_val, rpd_val = pipe.execute()

                rpm_used = int(rpm_val or 0)
                tpm_used = int(tpm_val or 0)
                rpd_used = int(rpd_val or 0)

                if rpd_used >= self.rpd_limit:
                    return False, 3600.0, f"daily_request_limit_exhausted ({rpd_used}/{self.rpd_limit} reqs today)"

                if rpm_used >= self.rpm_limit:
                    return False, seconds_left_in_minute, f"rpm_limit_reached ({rpm_used}/{self.rpm_limit} req/min)"

                if (tpm_used + estimated_tokens) > self.tpm_limit:
                    return False, seconds_left_in_minute, f"tpm_limit_reached ({tpm_used}/{self.tpm_limit} tokens/min)"

                return True, 0.0, "ok"
            except Exception as e:
                logger.warning(f"Error checking Redis rate limit: {e}")

        # In-memory fallback
        global _fallback_cooldown_until
        if now < _fallback_cooldown_until:
            rem = _fallback_cooldown_until - now
            return False, rem, f"rate_limit_cooldown ({int(rem)}s remaining)"

        rpm_used = _fallback_rpm.get(minute_bucket, 0)
        tpm_used = _fallback_tpm.get(minute_bucket, 0)
        rpd_used = _fallback_rpd.get(day_bucket, 0)

        if rpd_used >= self.rpd_limit:
            return False, 3600.0, f"daily_request_limit_exhausted ({rpd_used}/{self.rpd_limit})"
        if rpm_used >= self.rpm_limit:
            return False, seconds_left_in_minute, f"rpm_limit_reached ({rpm_used}/{self.rpm_limit})"
        if (tpm_used + estimated_tokens) > self.tpm_limit:
            return False, seconds_left_in_minute, f"tpm_limit_reached ({tpm_used}/{self.tpm_limit})"

        return True, 0.0, "ok"

    def record_call(self, tokens_used: int = 2000, key_identifier: Optional[str] = None):
        """
        Record usage after a successful or attempted Gemini API call.
        """
        now = time.time()
        minute_bucket = int(now // 60)
        day_bucket = time.strftime("%Y-%m-%d", time.gmtime(now))
        pfx = self._get_prefix(key_identifier)

        client = _get_redis_client()
        if client:
            try:
                pipe = client.pipeline()
                rpm_key = f"{pfx}:rpm:{minute_bucket}"
                tpm_key = f"{pfx}:tpm:{minute_bucket}"
                rpd_key = f"{pfx}:rpd:{day_bucket}"

                pipe.incr(rpm_key)
                pipe.expire(rpm_key, 120)
                pipe.incrby(tpm_key, tokens_used)
                pipe.expire(tpm_key, 120)
                pipe.incr(rpd_key)
                pipe.expire(rpd_key, 172800)
                pipe.execute()
                return
            except Exception as e:
                logger.warning(f"Error recording Redis rate limit: {e}")

        # In-memory fallback
        _fallback_rpm[minute_bucket] = _fallback_rpm.get(minute_bucket, 0) + 1
        _fallback_tpm[minute_bucket] = _fallback_tpm.get(minute_bucket, 0) + tokens_used
        _fallback_rpd[day_bucket] = _fallback_rpd.get(day_bucket, 0) + 1

    def record_rate_limit(self, cooldown_seconds: Optional[int] = None, key_identifier: Optional[str] = None):
        """
        Triggered when Gemini returns HTTP 429 or ResourceExhausted.
        Pauses requests for the specific user/key for the cooldown duration.
        """
        cd = cooldown_seconds or self.default_cooldown
        pfx = self._get_prefix(key_identifier)
        client = _get_redis_client()
        if client:
            try:
                client.set(f"{pfx}:cooldown", "1", ex=cd)
                logger.info(f"Set Gemini rate-limit cooldown for '{pfx}' in Redis for {cd} seconds.")
                return
            except Exception as e:
                logger.warning(f"Error setting cooldown in Redis: {e}")

        global _fallback_cooldown_until
        _fallback_cooldown_until = time.time() + cd
        logger.info(f"Set in-memory Gemini rate-limit cooldown for {cd} seconds.")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current status and backlog metrics for reporting in UI / API.
        """
        now = time.time()
        minute_bucket = int(now // 60)
        day_bucket = time.strftime("%Y-%m-%d", time.gmtime(now))

        rpm_used = 0
        tpm_used = 0
        rpd_used = 0
        cooldown_rem = 0

        client = _get_redis_client()
        if client:
            try:
                cooldown_ttl = client.ttl("gemini:limiter:cooldown")
                cooldown_rem = max(0, cooldown_ttl or 0)
                pipe = client.pipeline()
                pipe.get(f"gemini:limiter:rpm:{minute_bucket}")
                pipe.get(f"gemini:limiter:tpm:{minute_bucket}")
                pipe.get(f"gemini:limiter:rpd:{day_bucket}")
                rpm_v, tpm_v, rpd_v = pipe.execute()
                rpm_used = int(rpm_v or 0)
                tpm_used = int(tpm_v or 0)
                rpd_used = int(rpd_v or 0)
            except Exception:
                pass
        else:
            global _fallback_cooldown_until
            cooldown_rem = max(0, int(_fallback_cooldown_until - now))
            rpm_used = _fallback_rpm.get(minute_bucket, 0)
            tpm_used = _fallback_tpm.get(minute_bucket, 0)
            rpd_used = _fallback_rpd.get(day_bucket, 0)

        return {
            "rpm_used": rpm_used,
            "rpm_limit": self.rpm_limit,
            "tpm_used": tpm_used,
            "tpm_limit": self.tpm_limit,
            "rpd_used": rpd_used,
            "rpd_limit": self.rpd_limit,
            "is_rate_limited": cooldown_rem > 0 or rpm_used >= self.rpm_limit,
            "cooldown_remaining_seconds": cooldown_rem,
        }


gemini_limiter = GeminiRateLimiter()
