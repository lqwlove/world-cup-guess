"""Discussion lifecycle: create, run, persist, publish."""

import hashlib
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, desc, func, select
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
from app.services.analysis_result import extract_analysis_result
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
    auto_start: bool = True,
) -> Discussion:
    match = await session.get(Match, match_id)
    if not match:
        raise ValueError(f"Match {match_id} not found")

    key = cache_key(match_id, match.data_version)
    if auto_start and not force_refresh:
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
        status="pending" if auto_start else "draft",
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


async def list_discussions_for_match(
    session: AsyncSession, match_id: str
) -> list[dict[str, Any]]:
    msg_count = (
        select(
            DiscussionMessage.discussion_id,
            func.count(DiscussionMessage.id).label("message_count"),
        )
        .group_by(DiscussionMessage.discussion_id)
        .subquery()
    )
    result = await session.execute(
        select(
            Discussion,
            func.coalesce(msg_count.c.message_count, 0).label("message_count"),
            ConsensusArtifact.json_data,
        )
        .outerjoin(msg_count, Discussion.id == msg_count.c.discussion_id)
        .outerjoin(ConsensusArtifact, ConsensusArtifact.discussion_id == Discussion.id)
        .where(Discussion.match_id == match_id)
        .order_by(desc(Discussion.started_at), desc(Discussion.id))
    )
    rows: list[dict[str, Any]] = []
    for discussion, message_count, artifact_json in result.all():
        row: dict[str, Any] = {
            "id": discussion.id,
            "match_id": discussion.match_id,
            "status": discussion.status,
            "mode": getattr(discussion, "mode", "analysis") or "analysis",
            "phase": discussion.phase,
            "round": discussion.round,
            "started_at": discussion.started_at,
            "finished_at": discussion.finished_at,
            "error_reason": discussion.error_reason,
            "message_count": int(message_count or 0),
            "result_pick": None,
            "result_label": None,
            "result_pct": None,
            "result_score": None,
        }
        if artifact_json:
            extracted = extract_analysis_result(artifact_json)
            if extracted:
                row["result_pick"] = extracted["pick"]
                row["result_label"] = extracted["label"]
                row["result_pct"] = extracted["pct"]
                row["result_score"] = extracted.get("score")
        rows.append(row)
    return rows


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
        "max_turns": settings.max_rounds,
        "messages": [],
        "claims_registry": {},
        "valid_evidence_ids": [],
        "market_snapshot": {},
        "match_context": {},
        "specialist_outputs": {},
        "supervisor_trace": [],
        "unresolved": [],
        "claim_authors": {},
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
        discussion = await session.get(Discussion, discussion_id)
        if not discussion or discussion.status == "cancelled":
            break
        await _sync_discussion_row(session, discussion, state)

    return final_state


async def run_deliberation(session: AsyncSession, discussion_id: UUID) -> None:
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        return
    if discussion.status in ("cancelled", "completed"):
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

        if discussion.status == "cancelled":
            await publish_discussion_event(
                str(discussion_id),
                {
                    "type": "status",
                    "status": "cancelled",
                    "phase": discussion.phase,
                    "round": discussion.round,
                },
            )
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
        discussion = await session.get(Discussion, discussion_id)
        if not discussion or discussion.status == "cancelled":
            return
        discussion.status = "failed"
        discussion.error_reason = str(e)
        discussion.finished_at = datetime.utcnow()
        await session.commit()
        await publish_discussion_event(
            str(discussion_id),
            {"type": "error", "message": str(e)},
        )


async def start_discussion_run(
    session: AsyncSession, discussion_id: UUID
) -> Discussion:
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found")
    if discussion.status in ("running", "pending"):
        return discussion
    if discussion.status == "completed":
        raise ValueError("Discussion already completed")
    if discussion.status not in ("draft", "failed", "cancelled", "partial"):
        raise ValueError(f"Cannot start discussion in status {discussion.status}")

    if discussion.status in ("cancelled", "failed"):
        await clear_discussion_run(session, discussion_id)
        discussion = await session.get(Discussion, discussion_id)
        if not discussion:
            raise ValueError("Discussion not found")
        discussion.started_at = None
        discussion.round = 0
        discussion.phase = "Analysis"

    discussion.status = "pending"
    discussion.error_reason = None
    discussion.finished_at = None
    if not discussion.started_at:
        discussion.phase = "Analysis"
        discussion.round = 0
    await session.commit()
    await session.refresh(discussion)
    return discussion


async def stop_discussion_run(
    session: AsyncSession, discussion_id: UUID
) -> Discussion:
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        raise ValueError("Discussion not found")
    if discussion.status not in ("running", "pending"):
        raise ValueError("Discussion is not running")

    discussion.status = "cancelled"
    discussion.error_reason = None
    discussion.finished_at = datetime.utcnow()
    await session.commit()
    await session.refresh(discussion)
    await publish_discussion_event(
        str(discussion_id),
        {
            "type": "status",
            "status": "cancelled",
            "phase": discussion.phase,
            "round": discussion.round,
        },
    )
    return discussion


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
