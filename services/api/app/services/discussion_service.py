"""Discussion lifecycle: create, run, persist, publish."""

import hashlib
import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deliberation.graph import build_deliberation_graph
from app.models.entities import (
    ConsensusArtifact,
    Discussion,
    DiscussionMessage,
    Match,
    MatchFact,
)
from app.services.consensus_service import validate_consensus_artifact
from app.services.market_service import fetch_polymarket_snapshot
from app.services.redis_pubsub import publish_discussion_event

settings = get_settings()
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_deliberation_graph()
    return _graph


def cache_key(match_id: str, data_version: str) -> str:
    raw = f"{match_id}:{data_version}:{settings.prompt_version}:{settings.graph_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


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
        phase="Opening",
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
    """重试前清空该场合议消息与共识产物。"""
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


async def run_deliberation(session: AsyncSession, discussion_id: UUID) -> None:
    discussion = await session.get(Discussion, discussion_id)
    if not discussion:
        return

    match = await session.get(Match, discussion.match_id)
    if not match:
        return

    discussion.status = "running"
    discussion.started_at = datetime.utcnow()
    await session.commit()

    facts = await load_facts(session, discussion.match_id)
    valid_evidence_ids = [f["evidence_id"] for f in facts]

    snap = await fetch_polymarket_snapshot(session, discussion.match_id)
    market_probs = snap.probabilities if snap else {}

    initial_state = {
        "discussion_id": str(discussion_id),
        "match_id": discussion.match_id,
        "phase": "Opening",
        "round": 0,
        "max_rounds": settings.max_rounds,
        "messages": [],
        "claims_registry": {},
        "facts_bundle": facts,
        "market_snapshot": market_probs,
        "match_context": {
            "home_team": match.home_team,
            "away_team": match.away_team,
            "stage": match.stage,
        },
        "valid_evidence_ids": valid_evidence_ids,
        "challenge_streak": 0,
        "cross_exam_rounds": 0,
        "unresolved": [],
        "vote_open": False,
    }

    try:
        graph = get_graph()
        final_state: dict[str, Any] = dict(initial_state)
        persisted = 0

        async for state in graph.astream(initial_state, stream_mode="values"):
            final_state = state
            discussion.phase = state.get("phase", discussion.phase)
            discussion.round = state.get("round", discussion.round)
            msgs = state.get("messages", [])
            while persisted < len(msgs):
                await append_message(session, discussion_id, msgs[persisted])
                persisted += 1
            await publish_discussion_event(
                str(discussion_id),
                {
                    "type": "status",
                    "status": "running",
                    "phase": discussion.phase,
                    "round": discussion.round,
                },
            )

        artifact = final_state.get("final_artifact")
        status = final_state.get("status", "PARTIAL_CONSENSUS")

        failed_validation = False
        if artifact:
            ok, err = validate_consensus_artifact(artifact)
            if not ok:
                failed_validation = True
                discussion.status = "failed"
                discussion.error_reason = f"共识 Schema 校验失败: {err}"
                artifact["status"] = "PARTIAL_CONSENSUS"
                artifact["consensus_strength"] = "partial"
                status = "PARTIAL_CONSENSUS"

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

        if not failed_validation:
            discussion.status = "completed" if status == "CONSENSUS_FINAL" else "partial"
        discussion.phase = final_state.get("phase", "Consensus")
        discussion.round = final_state.get("round", 0)
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
        if artifact:
            await publish_discussion_event(
                str(discussion_id),
                {"type": "consensus", "artifact": artifact},
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
