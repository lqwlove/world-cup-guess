import json
from typing import Any

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()
_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(settings.redis_url, decode_responses=True)
    return _pool


def channel_name(discussion_id: str) -> str:
    return f"discussion:{discussion_id}"


async def publish_discussion_event(discussion_id: str, payload: dict[str, Any]) -> None:
    r = await get_redis()
    await r.publish(channel_name(discussion_id), json.dumps(payload, ensure_ascii=False))


async def enqueue_deliberation(discussion_id: str) -> None:
    r = await get_redis()
    await r.lpush("deliberation_queue", discussion_id)
