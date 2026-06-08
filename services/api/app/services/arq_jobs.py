"""Enqueue background jobs to ARQ."""

import logging

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def enqueue_arq_job(job_name: str, *args: str) -> bool:
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job(job_name, *args)
        await redis.close()
        return True
    except Exception as exc:
        logger.exception("Failed to enqueue ARQ job %s: %s", job_name, exc)
        return False
