import asyncio
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.db import get_session
from app.models.entities import Discussion, Match
from app.schemas.consensus import ConsensusArtifactOut
from app.schemas.discussion import (
    DiscussionCreate,
    DiscussionListItem,
    DiscussionOut,
    FollowupChat,
    MessageOut,
    ResumeDiscussion,
)
from app.services.arq_jobs import enqueue_arq_job
from app.services.consensus_service import get_consensus_for_discussion
from app.services.discussion_service import (
    clear_discussion_run,
    create_discussion,
    get_latest_discussion,
    get_messages,
    list_discussions_for_match,
    prepare_followup_chat,
    prepare_resume_discussion,
    run_deliberation,
)
from app.services.redis_pubsub import channel_name, enqueue_deliberation, get_redis

router = APIRouter(prefix="/api", tags=["discussions"])
settings = get_settings()


@router.post("/matches/{match_id}/discussions", response_model=DiscussionOut)
async def start_discussion(
    match_id: str,
    body: DiscussionCreate,
    session: AsyncSession = Depends(get_session),
):
    if not await session.get(Match, match_id):
        raise HTTPException(404, "Match not found")

    discussion = await create_discussion(session, match_id, force_refresh=body.force_refresh)
    if discussion.status == "completed":
        return _to_out(discussion)

    discussion.status = "pending"
    await session.commit()
    if not await enqueue_arq_job("run_deliberation_task", str(discussion.id)):
        raise HTTPException(503, "后台任务队列不可用，请确认 Redis 与 ARQ worker 已启动")

    return _to_out(discussion)


@router.post("/discussions/{discussion_id}/retry", response_model=DiscussionOut)
async def retry_discussion(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        raise HTTPException(404, "Discussion not found")
    await clear_discussion_run(session, discussion_id)
    discussion.status = "pending"
    discussion.phase = "Analysis"
    discussion.mode = "analysis"
    discussion.round = 0
    discussion.error_reason = None
    discussion.started_at = None
    discussion.finished_at = None
    await session.commit()
    await enqueue_deliberation(str(discussion.id))
    if not await enqueue_arq_job("run_deliberation_task", str(discussion_id)):
        raise HTTPException(503, "后台任务队列不可用，请确认 Redis 与 ARQ worker 已启动")
    return _to_out(discussion)


@router.get("/matches/{match_id}/discussions", response_model=list[DiscussionListItem])
async def list_match_discussions(
    match_id: str,
    session: AsyncSession = Depends(get_session),
):
    if not await session.get(Match, match_id):
        raise HTTPException(404, "Match not found")
    rows = await list_discussions_for_match(session, match_id)
    return [DiscussionListItem(**row) for row in rows]


@router.get("/matches/{match_id}/discussions/latest", response_model=DiscussionOut)
async def latest_match_discussion(
    match_id: str,
    session: AsyncSession = Depends(get_session),
):
    if not await session.get(Match, match_id):
        raise HTTPException(404, "Match not found")
    discussion = await get_latest_discussion(session, match_id)
    if not discussion:
        raise HTTPException(404, "No discussion for this match")
    return _to_out(discussion)


@router.get("/discussions/{discussion_id}", response_model=DiscussionOut)
async def get_discussion(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        raise HTTPException(404, "Discussion not found")
    return _to_out(discussion)


@router.get("/discussions/{discussion_id}/consensus", response_model=ConsensusArtifactOut)
async def get_discussion_consensus(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    if not await session.get(Discussion, discussion_id):
        raise HTTPException(404, "Discussion not found")
    consensus = await get_consensus_for_discussion(session, discussion_id)
    if not consensus:
        raise HTTPException(404, "No consensus for this discussion")
    return consensus


@router.get("/discussions/{discussion_id}/messages", response_model=list[MessageOut])
async def list_messages(
    discussion_id: UUID,
    from_seq: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    if not await session.get(Discussion, discussion_id):
        raise HTTPException(404, "Discussion not found")
    messages = await get_messages(session, discussion_id, from_seq)
    return [
        MessageOut(
            seq=m.seq,
            role=m.role,
            msg_type=m.msg_type,
            content=m.content,
            refs=m.refs or [],
            evidence_ids=m.evidence_ids or [],
            phase=m.phase,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.get("/discussions/{discussion_id}/stream")
async def stream_discussion(discussion_id: UUID):
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(channel_name(str(discussion_id)))

    async def event_generator():
        # Replay hint: client should fetch /messages first
        yield {"event": "connected", "data": json.dumps({"discussion_id": str(discussion_id)})}
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
                if message and message.get("type") == "message":
                    yield {"event": "message", "data": message["data"]}
                else:
                    yield {"event": "ping", "data": "{}"}
                await asyncio.sleep(0.05)
        finally:
            await pubsub.unsubscribe(channel_name(str(discussion_id)))
            await pubsub.close()

    return EventSourceResponse(event_generator())


@router.post("/discussions/{discussion_id}/resume", response_model=DiscussionOut)
async def resume_discussion_endpoint(
    discussion_id: UUID,
    body: ResumeDiscussion,
    session: AsyncSession = Depends(get_session),
):
    if not body.reply.strip():
        raise HTTPException(400, "reply is required")
    try:
        discussion = await prepare_resume_discussion(
            session, discussion_id, body.reply.strip()
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not await enqueue_arq_job(
        "resume_discussion_task", str(discussion_id), body.reply.strip()
    ):
        raise HTTPException(503, "后台任务队列不可用，请确认 Redis 与 ARQ worker 已启动")
    return _to_out(discussion)


@router.post("/discussions/{discussion_id}/chat", response_model=DiscussionOut)
async def followup_chat_endpoint(
    discussion_id: UUID,
    body: FollowupChat,
    session: AsyncSession = Depends(get_session),
):
    if not body.question.strip():
        raise HTTPException(400, "question is required")
    try:
        discussion = await prepare_followup_chat(
            session, discussion_id, body.question.strip()
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if not await enqueue_arq_job(
        "followup_chat_task", str(discussion_id), body.question.strip()
    ):
        raise HTTPException(503, "后台任务队列不可用，请确认 Redis 与 ARQ worker 已启动")
    return _to_out(discussion)


@router.post("/discussions/{discussion_id}/run-sync")
async def run_sync(
    discussion_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Dev endpoint: run deliberation in-process without worker."""
    if not await session.get(Discussion, discussion_id):
        raise HTTPException(404, "Discussion not found")
    await run_deliberation(session, discussion_id)
    discussion = await session.get(Discussion, discussion_id)
    return _to_out(discussion)


def _to_out(d: Discussion) -> DiscussionOut:
    return DiscussionOut(
        id=d.id,
        match_id=d.match_id,
        status=d.status,
        mode=getattr(d, "mode", "analysis") or "analysis",
        phase=d.phase,
        round=d.round,
        started_at=d.started_at,
        finished_at=d.finished_at,
        error_reason=d.error_reason,
    )
