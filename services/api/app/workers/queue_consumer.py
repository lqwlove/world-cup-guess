"""Optional Redis list consumer for deliberation_queue fallback."""

import asyncio
from uuid import UUID

from app.db import async_session_factory
from app.services.discussion_service import run_deliberation
from app.services.redis_pubsub import get_redis


async def consume_deliberation_queue(poll_interval: float = 2.0) -> None:
    while True:
        try:
            r = await get_redis()
            item = await r.brpop("deliberation_queue", timeout=5)
            if item:
                _, discussion_id = item
                async with async_session_factory() as session:
                    await run_deliberation(session, UUID(discussion_id))
        except Exception:
            pass
        await asyncio.sleep(poll_interval)
