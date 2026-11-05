from functools import lru_cache

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from supabase import Client, create_client

from app.core.config import settings

# auto_error=False so a missing token is a 401 (not FastAPI's default 403).
_bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _supabase_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


def get_supabase() -> Client:
    """Shared service-role client. It bypasses RLS, so every route that uses it
    must enforce authorisation itself (see app.core.access)."""
    return _supabase_client()


_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """One shared connection pool for the process (was: a new pool per request)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


def verify_token(supabase: Client, token: str):
    """Return the Supabase user for a JWT, or raise ValueError."""
    try:
        user = supabase.auth.get_user(token).user
    except Exception as exc:  # noqa: BLE001 - any failure means "not authenticated"
        raise ValueError("invalid token") from exc
    if user is None:
        raise ValueError("invalid token")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    supabase: Client = Depends(get_supabase),
):
    """Authenticated organiser. Sync on purpose: FastAPI runs it in a threadpool,
    so the network call to Supabase Auth does not block the event loop."""
    unauthorised = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorised
    try:
        return verify_token(supabase, credentials.credentials)
    except ValueError:
        raise unauthorised from None


def rate_limit(name: str, limit: int, window_seconds: int):
    """Fixed-window per-IP limiter for unauthenticated routes.

    Fails open if Redis is unavailable: losing rate limiting is better than
    taking payments offline. Behind a proxy, run uvicorn with --proxy-headers so
    request.client reflects the real client address.
    """

    async def dependency(request: Request, redis: aioredis.Redis = Depends(get_redis)):
        ip = request.client.host if request.client else "unknown"
        key = f"rl:{name}:{ip}"
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, window_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"rate limiter unavailable ({name}): {exc}")
            return
        if count > limit:
            raise HTTPException(status_code=429, detail="Too many requests")

    return dependency
