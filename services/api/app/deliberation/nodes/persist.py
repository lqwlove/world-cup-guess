"""Persist new messages from graph state to PostgreSQL."""

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select

from app.deliberation.runtime import get_session
from app.deliberation.state import WarRoomState
from app.models.entities import DiscussionMessage
from app.services.redis_pubsub import publish_discussion_event


async def persist_node(state: WarRoomState) -> dict[str, Any]:
    session = get_session()
    discussion_id = UUID(state["discussion_id"])
    messages = state.get("messages", [])
    persisted = state.get("persisted_count", 0)

    while persisted < len(messages):
        msg = messages[persisted]
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
        persisted += 1

    return {"persisted_count": persisted}
