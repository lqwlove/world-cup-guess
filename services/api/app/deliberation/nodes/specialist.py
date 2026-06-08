"""Run a specialist agent with LangChain tool-calling."""

import json
from typing import Any

from app.deliberation.activity import publish_agent_analyzing, publish_agent_idle
from app.deliberation.agents.specialist_agent import run_specialist_agent
from app.deliberation.constants import SPECIALIST_ROLES
from app.deliberation.match_brief import is_vacuous_content
from app.deliberation.rules import validate_message
from app.deliberation.state import WarRoomState
from app.deliberation.tools.facts import reload_evidence_ids


def _tool_trace_messages(role: str, phase: str, tool_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for i, item in enumerate(tool_trace):
        msgs.append(
            {
                "role": role,
                "msg_type": "TOOL_CALL",
                "content": json.dumps(
                    {
                        "tool": item.get("tool", ""),
                        "args": item.get("args") or {},
                        "result_preview": item.get("result_preview", ""),
                        "index": i + 1,
                    },
                    ensure_ascii=False,
                ),
                "refs": [],
                "evidence_ids": [],
                "phase": phase,
            }
        )
    return msgs


async def specialist_node(state: WarRoomState) -> dict[str, Any]:
    role = state.get("next_role")
    if role not in SPECIALIST_ROLES:
        return {"error": f"invalid next_role: {role}"}

    discussion_id = state.get("discussion_id", "")
    if discussion_id:
        await publish_agent_analyzing(discussion_id, role)

    raw_msg = await run_specialist_agent(role, state)
    tool_trace = raw_msg.pop("_tool_trace", [])
    aggregated = raw_msg.pop("_aggregated", {})

    msg = {k: v for k, v in raw_msg.items() if not k.startswith("_")}
    msg["role"] = role
    msg["phase"] = state.get("phase", "Analysis")

    if state.get("mode") == "followup":
        user_q = state.get("user_reply") or ""
        if user_q and is_vacuous_content(msg.get("content", "")):
            msg["content"] = f"针对你的问题「{user_q[:80]}」：{msg.get('content', '')}"

    valid_evidence_ids = await reload_evidence_ids(state["match_id"])
    valid = set(valid_evidence_ids or state.get("valid_evidence_ids", []))

    result = validate_message(
        msg,
        phase=state.get("phase", "Analysis"),
        valid_evidence_ids=valid,
    )
    if not result.ok:
        from app.deliberation.match_brief import fallback_statement

        ctx = state.get("match_context", {})
        text, evs = fallback_statement(role, ctx, aggregated, list(valid))
        msg = {
            "role": role,
            "msg_type": "STATEMENT",
            "content": text,
            "evidence_ids": evs,
            "refs": [],
            "phase": msg["phase"],
        }

    messages = list(state.get("messages", []))
    claim_idx = len(state.get("claims_registry", {}))
    if msg.get("msg_type") == "STATEMENT" and msg.get("content"):
        claim_idx += 1
        msg["claim_id"] = f"E-{claim_idx:03d}"

    messages.extend(_tool_trace_messages(role, msg["phase"], tool_trace))
    messages.append(msg)

    if discussion_id:
        await publish_agent_idle(discussion_id, role)
    registry = dict(state.get("claims_registry", {}))
    if msg.get("claim_id"):
        registry[msg["claim_id"]] = msg.get("content", "")[:120]

    outputs = dict(state.get("specialist_outputs", {}))
    outputs[role] = {
        "tool_trace": tool_trace,
        "aggregated": aggregated,
        "summary": msg.get("content", "")[:500],
    }

    updates: dict[str, Any] = {
        "messages": messages,
        "claims_registry": registry,
        "specialist_outputs": outputs,
        "valid_evidence_ids": list(valid),
        "turn": state.get("turn", 0) + 1,
        "next_role": None,
    }

    if role == "market" and isinstance(aggregated, dict) and aggregated.get("probabilities"):
        probs = aggregated["probabilities"]
        updates["match_context"] = {
            **state.get("match_context", {}),
            "market_snapshot": probs,
            "market_available": True,
        }
        updates["market_snapshot"] = probs

    return updates
