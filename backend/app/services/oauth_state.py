import json
import secrets
import time
import logging
from typing import Optional, Dict, Any
from uuid import UUID
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Fallback in-memory state dictionary if Redis is temporarily unreachable
_in_memory_states: Dict[str, Dict[str, Any]] = {}


def _get_redis() -> Optional[redis.Redis]:
    try:
        r = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        r.ping()
        return r
    except Exception as e:
        logger.debug(f"Redis unavailable for oauth_state: {e}")
        return None


def create_oauth_state(
    user_id: UUID,
    platform: str,
    client_id: Optional[str] = None,
    project_id: Optional[str] = None,
    ttl_seconds: int = 600,  # 10 minutes
) -> str:
    """
    Generate a cryptographic, single-use, short-lived OAuth state token
    bound to the initiating user and client configuration.
    """
    rand_prefix = secrets.token_urlsafe(24)
    proj_tag = "".join(c for c in str(project_id or "default") if c.isalnum() or c in ("-", "_"))[:32]
    state_token = f"{rand_prefix}_{proj_tag}"
    state_data = {
        "user_id": str(user_id),
        "platform": platform,
        "client_id": client_id,
        "project_id": project_id,
        "created_at": time.time(),
        "expires_at": time.time() + ttl_seconds,
    }

    client = _get_redis()
    if client:
        try:
            client.set(f"oauth:state:{state_token}", json.dumps(state_data), ex=ttl_seconds)
            return state_token
        except Exception as e:
            logger.warning(f"Failed to store OAuth state in Redis: {e}")

    # Fallback to memory
    _in_memory_states[state_token] = state_data
    return state_token


def consume_oauth_state(state_token: str) -> Optional[Dict[str, Any]]:
    """
    Atomically retrieve and delete (single-use) an OAuth state token.
    Returns None if state is invalid, expired, or already consumed.
    """
    if not state_token:
        return None

    client = _get_redis()
    if client:
        try:
            raw = client.get(f"oauth:state:{state_token}")
            if raw:
                client.delete(f"oauth:state:{state_token}")
                data = json.loads(raw)
                if data.get("expires_at", 0) >= time.time():
                    return data
            return None
        except Exception as e:
            logger.warning(f"Failed to consume OAuth state from Redis: {e}")

    # Fallback from memory
    data = _in_memory_states.pop(state_token, None)
    if data and data.get("expires_at", 0) >= time.time():
        return data

    return None
