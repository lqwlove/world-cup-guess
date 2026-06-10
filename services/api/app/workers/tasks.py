"""ARQ task definitions."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.config import get_settings
from app.db import async_session_factory
from app.models.entities import Discussion, MarketMapping, Match
from app.services.discussion_service import (
    create_discussion,
    execute_followup_chat,
    execute_resume_discussion,
    run_deliberation,
)
from app.services.market_service import fetch_polymarket_snapshot
from arq import create_pool
from arq.connections import RedisSettings

settings = get_settings()


async def run_deliberation_task(ctx, discussion_id: str) -> str:
    async with async_session_factory() as session:
        await run_deliberation(session, UUID(discussion_id))
    return discussion_id


async def resume_discussion_task(ctx, discussion_id: str, user_reply: str) -> str:
    async with async_session_factory() as session:
        await execute_resume_discussion(session, UUID(discussion_id), user_reply)
    return discussion_id


async def followup_chat_task(ctx, discussion_id: str, question: str) -> str:
    async with async_session_factory() as session:
        await execute_followup_chat(session, UUID(discussion_id), question)
    return discussion_id


async def refresh_market_snapshots(ctx) -> int:
    if not settings.polymarket_fetch_enabled:
        return 0
    count = 0
    async with async_session_factory() as session:
        result = await session.execute(select(MarketMapping))
        for mapping in result.scalars().all():
            snap = await fetch_polymarket_snapshot(session, mapping.match_id)
            if snap:
                count += 1
    return count


async def pregenerate_hot_matches(ctx) -> int:
    """P2: pre-generate deliberations for hot matches within 24h of kickoff."""
    hot_ids = [x.strip() for x in settings.hot_match_ids.split(",") if x.strip()]
    window = timedelta(hours=settings.hot_match_pregen_hours)
    now = datetime.utcnow()
    created = 0

    async with async_session_factory() as session:
        for match_id in hot_ids:
            match = await session.get(Match, match_id)
            if not match:
                continue
            if match.kickoff_at > now + window * 4:
                continue

            result = await session.execute(
                select(Discussion).where(
                    Discussion.match_id == match_id,
                    Discussion.status.in_(["running", "completed", "pending"]),
                )
            )
            if result.scalars().first():
                continue

            discussion = await create_discussion(session, match_id)
            try:
                redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
                await redis.enqueue_job("run_deliberation_task", str(discussion.id))
                await redis.close()
            except Exception:
                pass
            created += 1

    return created
