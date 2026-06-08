"""Discussion lifecycle: create, run, persist, publish."""

import hashlib
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deliberation.graph_v2 import get_compiled_graph, graph_config
from app.deliberation.runtime import bind_session
from app.models.entities import (
    ConsensusArtifact,
    Discussion,
    DiscussionMessage,
    Match,
    MatchFact,
)
from app.services.consensus_service import validate_consensus_artifact
from app.services.redis_pubsub import publish_discussion_event

settings = get_settings()


def cache_key(match_id: str, data_version: str) -> str:
    raw = f"{match_id}:{data_version}:{settings.prompt_version}:{settings.graph_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _messages_from_db(rows: list[DiscussionMessage]) -> list[dict[str, Any]]:
    return [
        {
            "role": m.role,
            "msg_type": m.msg_type,
            "content": m.content,
            "refs": m.refs or [],
            "evidence_ids": m.evidence_ids or [],
            "phase": m.phase,
        }
        for m in rows
    ]


async def create_discussion(
    session: AsyncSession,
    match_id: str,
    *,
    force_refresh: bool = False,
) -> Discussion:
    match = await session.get(Match, match_id)
    if not match:
        raise ValueError(f"Match {match_id} not found")

    key = cache_key(match_id, match.data_version)
    if not force_refresh:
        result = await session.execute(
            select(Discussion).where(
                Discussion.match_id == match_id,
                Discussion.cache_key == key,
                Discussion.status == "completed",
            )
        )
        cached = result.scalar_one_or_none()
        if cached:
            return cached

    discussion = Discussion(
        match_id=match_id,
        status="pending",
        mode="analysis",
        phase="Analysis",
        round=0,
        data_version=match.data_version,
        cache_key=key,
    )
    session.add(discussion)
    await session.commit()
    await session.refresh(discussion)
    return discussion


async def get_latest_discussion(
    session: AsyncSession, match_id: str
) -> Optional[Discussion]:
    result = await session.execute(
        select(Discussion)
        .where(Discussion.match_id == match_id)
        .order_by(desc(Discussion.started_at), desc(Discussion.id))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def clear_discussion_run(session: AsyncSession, discussion_id: UUID) -> None:
    await session.execute(
        delete(DiscussionMessage).where(DiscussionMessage.discussion_id == discussion_id)
    )
    await session.execute(
        delete(ConsensusArtifact).where(ConsensusArtifact.discussion_id == discussion_id)
    )


async def append_message(
    session: AsyncSession,
    discussion_id: UUID,
    msg: dict[str, Any],
) -> DiscussionMessage:
    result = await session.execute(
        select(DiscussionMessage)
        .where(DiscussionMessage.discussion_id == discussion_id)
        .order_by(desc(DiscussionMessage.seq))
        .limit(1)
    )
    last = result.scalar_one_or_none()
    seq = (last.seq if last else 0) + 1
    db_msg = DiscussionMessage(
        discussion_id=discussion_id,
        seq=seq,
        role=msg.get("role", "unknown"),
        msg_type=msg.get("msg_type", "STATEMENT"),
        content=msg.get("content", ""),
        refs=msg.get("refs", []),
        evidence_ids=msg.get("evidence_ids", []),
        phase=msg.get("phase", ""),
    )
    session.add(db_msg)
    await session.commit()
    await session.refresh(db_msg)
    await publish_discussion_event(
        str(discussion_id),
        {
            "type": "message",
            "seq": seq,
            "role": db_msg.role,
            "msg_type": db_msg.msg_type,
            "content": db_msg.content,
            "refs": db_msg.refs,
            "evidence_ids": db_msg.evidence_ids,
            "phase": db_msg.phase,
        },
    )
    return db_msg


async def load_facts(session: AsyncSession, match_id: str) -> list[dict[str, Any]]:
    result = await session.execute(select(MatchFact).where(MatchFact.match_id == match_id))
    facts = result.scalars().all()
    return [
        {
            "fact_type": f.fact_type,
            "payload": f.payload,
            "evidence_id": f.evidence_id,
            "source": f.source,
        }
        for f in facts
    ]


async def _sync_discussion_row(
    session: AsyncSession,
    discussion: Discussion,
    state: dict[str, Any],
) -> None:
    discussion.phase = state.get("phase", discussion.phase)
    discussion.round = state.get("turn", state.get("round", discussion.round))
    discussion.mode = state.get("mode", discussion.mode)
    status = state.get("status")
    if status in ("running", "awaiting_user", "completed", "partial", "failed"):
        discussion.status = status
    await session.commit()
    await publish_discussion_event(
        str(discussion.id),
        {
            "type": "status",
            "status": discussion.status,
            "phase": discussion.phase,
            "round": discussion.round,
            "mode": discussion.mode,
        },
    )


async def _finalize_artifact(
    session: AsyncSession,
    discussion: Discussion,
    discussion_id: UUID,
    final_state: dict[str, Any],
) -> None:
    artifact = final_state.get("final_artifact")
    if not artifact:
        return

    ok, err = validate_consensus_artifact(artifact)
    if not ok:
        discussion.status = "failed"
        discussion.error_reason = f"共识 Schema 校验失败: {err}"
        artifact["status"] = "PARTIAL_CONSENSUS"
        artifact["consensus_strength"] = "partial"

    await session.execute(
        delete(ConsensusArtifact).where(ConsensusArtifact.discussion_id == discussion_id)
    )
    strength = artifact.get("consensus_strength", "weak")
    session.add(
        ConsensusArtifact(
            match_id=discussion.match_id,
            discussion_id=discussion_id,
            schema_version="v1",
            json_data=artifact,
            strength=strength,
        )
    )
    await session.commit()
    await publish_discussion_event(
        str(discussion_id),
        {"type": "consensus", "artifact": artifact},
    )


def _initial_state(discussion: Discussion) -> dict[str, Any]:
    return {
        "discussion_id": str(discussion.id),
        "match_id": discussion.match_id,
        "mode": "analysis",
        "status": "running",
        "phase": "Analysis",
        "turn": 0,
        "max_turns": settings.max_turns,
        "messages": [],
        "claims_registry": {},
        "valid_evidence_ids": [],
        "market_snapshot": {},
        "match_context": {},
        "specialist_outputs": {},
        "supervisor_trace": [],
        "unresolved": [],
        "awaiting_user": False,
        "persisted_count": 0,
        "resume_to_supervisor": False,
    }


async def _run_graph_stream(
    session: AsyncSession,
    discussion_id: UUID,
    graph_input: dict[str, Any],
) -> dict[str, Any]:
    bind_session(session)
    graph = await get_compiled_graph()
    config = graph_config(str(discussion_id))
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        return {}

    final_state: dict[str, Any] = {}
    async for state in graph.astream(graph_input, config, stream_mode="values"):
        final_state = state
        await _sync_discussion_row(session, discussion, state)

    return final_state


async def run_deliberation(session: AsyncSession, discussion_id: UUID) -> None:
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        return

    match = await session.get(Match, discussion.match_id)
    if not match:
        return

    discussion.status = "running"
    discussion.mode = "analysis"
    discussion.phase = "Analysis"
    discussion.started_at = datetime.utcnow()
    await session.commit()

    try:
        final_state = await _run_graph_stream(
            session,
            discussion_id,
            _initial_state(discussion),
        )

        discussion = await session.get(Discussion, discussion_id)
        if not discussion:
            return

        if final_state.get("status") == "completed":
            await _finalize_artifact(session, discussion, discussion_id, final_state)
            discussion.finished_at = datetime.utcnow()
        elif final_state.get("status") == "awaiting_user":
            discussion.status = "awaiting_user"
        elif final_state.get("status") not in ("failed",):
            if not final_state.get("awaiting_user"):
                discussion.status = discussion.status or "partial"
                discussion.finished_at = datetime.utcnow()

        await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {
                "type": "status",
                "status": discussion.status,
                "phase": discussion.phase,
                "round": discussion.round,
            },
        )
    except Exception as e:
        discussion.status = "failed"
        discussion.error_reason = str(e)
        discussion.finished_at = datetime.utcnow()
        await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {"type": "error", "message": str(e)},
        )


async def prepare_resume_discussion(
    session: AsyncSession,
    discussion_id: UUID,
    user_reply: str,
) -> Discussion:
    """Fast path: persist user reply and mark discussion running (API returns immediately)."""
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found")
    if discussion.status != "awaiting_user":
        raise ValueError("Discussion is not awaiting user input")

    text = user_reply.strip()
    if not text:
        raise ValueError("reply is required")

    user_msg = {
        "role": "user",
        "msg_type": "USER_REPLY",
        "content": text,
        "refs": [],
        "evidence_ids": [],
        "phase": discussion.phase,
    }
    await append_message(session, discussion_id, user_msg)

    discussion.status = "running"
    discussion.mode = "analysis"
    discussion.error_reason = None
    await session.commit()
    await session.refresh(discussion)
    await publish_discussion_event(
        str(discussion_id),
        {
            "type": "status",
            "status": discussion.status,
            "phase": discussion.phase,
            "round": discussion.round,
            "mode": discussion.mode,
        },
    )
    return discussion


async def execute_resume_discussion(
    session: AsyncSession,
    discussion_id: UUID,
    user_reply: str,
) -> None:
    """Worker path: continue graph after user answered supervisor."""
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        return

    rows = await get_messages(session, discussion_id)
    text = user_reply.strip()

    try:
        final_state = await _run_graph_stream(
            session,
            discussion_id,
            {
                "user_reply": text,
                "awaiting_user": False,
                "status": "running",
                "resume_to_supervisor": True,
                "messages": _messages_from_db(rows),
                "persisted_count": len(rows),
                "mode": "analysis",
            },
        )

        discussion = await session.get(Discussion, discussion_id)
        if not discussion:
            return

        if final_state.get("status") == "completed":
            await _finalize_artifact(session, discussion, discussion_id, final_state)
            discussion.finished_at = datetime.utcnow()
        elif final_state.get("status") == "awaiting_user":
            discussion.status = "awaiting_user"
        elif final_state.get("status") not in ("failed",):
            discussion.finished_at = datetime.utcnow()

        await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {
                "type": "status",
                "status": discussion.status,
                "phase": discussion.phase,
                "round": discussion.round,
            },
        )
    except Exception as e:
        discussion = await session.get(Discussion, discussion_id)
        if discussion:
            discussion.status = "failed"
            discussion.error_reason = str(e)
            discussion.finished_at = datetime.utcnow()
            await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {"type": "error", "message": str(e)},
        )


async def resume_discussion(
    session: AsyncSession,
    discussion_id: UUID,
    user_reply: str,
) -> Discussion:
    """Sync/dev: prepare + execute in one call."""
    discussion = await prepare_resume_discussion(session, discussion_id, user_reply)
    await execute_resume_discussion(session, discussion_id, user_reply)
    await session.refresh(discussion)
    discussion = await session.get(Discussion, discussion_id)
    return discussion


async def prepare_followup_chat(
    session: AsyncSession,
    discussion_id: UUID,
    question: str,
) -> Discussion:
    """Fast path: persist user question and mark discussion running."""
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found")
    if discussion.status not in ("completed", "partial"):
        raise ValueError("Discussion analysis not finished")

    text = question.strip()
    if not text:
        raise ValueError("question is required")

    user_msg = {
        "role": "user",
        "msg_type": "USER_REPLY",
        "content": text,
        "refs": [],
        "evidence_ids": [],
        "phase": "FollowUp",
    }
    await append_message(session, discussion_id, user_msg)

    discussion.status = "running"
    discussion.mode = "followup"
    discussion.phase = "FollowUp"
    discussion.error_reason = None
    await session.commit()
    await session.refresh(discussion)
    await publish_discussion_event(
        str(discussion_id),
        {
            "type": "status",
            "status": discussion.status,
            "phase": discussion.phase,
            "round": discussion.round,
            "mode": discussion.mode,
        },
    )
    return discussion


async def execute_followup_chat(
    session: AsyncSession,
    discussion_id: UUID,
    question: str,
) -> None:
    """Worker path: supervisor routes follow-up to a specialist."""
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        return

    rows = await get_messages(session, discussion_id)
    text = question.strip()

    try:
        final_state = await _run_graph_stream(
            session,
            discussion_id,
            {
                "mode": "followup",
                "user_reply": text,
                "status": "running",
                "resume_to_supervisor": True,
                "messages": _messages_from_db(rows),
                "persisted_count": len(rows),
                "phase": "FollowUp",
            },
        )

        discussion = await session.get(Discussion, discussion_id)
        if not discussion:
            return

        discussion.status = "completed"
        discussion.mode = "followup"
        discussion.phase = final_state.get("phase", "FollowUp")
        await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {
                "type": "status",
                "status": discussion.status,
                "phase": discussion.phase,
                "round": discussion.round,
            },
        )
    except Exception as e:
        discussion = await session.get(Discussion, discussion_id)
        if discussion:
            discussion.status = "failed"
            discussion.error_reason = str(e)
            discussion.finished_at = datetime.utcnow()
            await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {"type": "error", "message": str(e)},
        )


async def followup_chat(
    session: AsyncSession,
    discussion_id: UUID,
    question: str,
) -> Discussion:
    """Sync/dev: prepare + execute in one call."""
    discussion = await prepare_followup_chat(session, discussion_id, question)
    await execute_followup_chat(session, discussion_id, question)
    await session.refresh(discussion)
    discussion = await session.get(Discussion, discussion_id)
    return discussion


async def get_messages(
    session: AsyncSession, discussion_id: UUID, from_seq: int = 0
) -> list[DiscussionMessage]:
    result = await session.execute(
        select(DiscussionMessage)
        .where(
            DiscussionMessage.discussion_id == discussion_id,
            DiscussionMessage.seq >= from_seq,
        )
        .order_by(DiscussionMessage.seq)
    )
    return list(result.scalars().all())
