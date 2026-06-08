"""Real-time agent activity events for the war-room chat UI."""

from typing import Any

from app.services.redis_pubsub import publish_discussion_event


async def publish_agent_analyzing(discussion_id: str, role: str) -> None:
    await publish_discussion_event(
        discussion_id,
        {"type": "agent_analyzing", "role": role},
    )


async def publish_tool_call(
    discussion_id: str,
    *,
    role: str,
    tool: str,
    args: dict[str, Any] | None = None,
    result_preview: str = "",
    index: int = 0,
) -> None:
    await publish_discussion_event(
        discussion_id,
        {
            "type": "tool_call",
            "role": role,
            "tool": tool,
            "args": args or {},
            "result_preview": result_preview[:400],
            "index": index,
        },
    )


async def publish_agent_idle(discussion_id: str, role: str) -> None:
    await publish_discussion_event(
        discussion_id,
        {"type": "agent_idle", "role": role},
    )
