"""Run a specialist agent with role-specific tools."""

import json
from typing import Any

from app.config import get_settings
from app.deliberation.constants import ROLE_LABELS, SPECIALIST_ROLES
from app.deliberation.llm import call_llm_json, generate_role_message
from app.deliberation.rules import validate_message
from app.deliberation.state import WarRoomState
from app.deliberation.tools import run_data_tools, run_market_tools, run_squad_tools

settings = get_settings()


async def _run_tools(role: str, match_id: str) -> dict[str, Any]:
    if role == "data":
        return await run_data_tools(match_id)
    if role == "squad":
        return await run_squad_tools(match_id)
    if role == "market":
        return await run_market_tools(match_id)
    return {}


def _format_tool_context(role: str, tool_result: dict[str, Any]) -> str:
    if not tool_result:
        return "（无工具数据）"
    return json.dumps(tool_result, ensure_ascii=False)[:4000]


async def _generate_with_tools(
    role: str,
    state: WarRoomState,
    tool_result: dict[str, Any],
) -> dict[str, Any]:
    if settings.mock_llm:
        return await generate_role_message(
            role=role,
            phase=state.get("phase", "Analysis"),
            match_context={
                **state.get("match_context", {}),
                "tool_result": tool_result,
            },
            recent_messages=state.get("messages", []),
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )

    label = ROLE_LABELS.get(role, role)
    home = state.get("match_context", {}).get("home_team", "")
    away = state.get("match_context", {}).get("away_team", "")
    prompt = f"""你是【{label}】（{role}）。对阵 {home} vs {away}。
你已调用工具获取数据：
{_format_tool_context(role, tool_result)}

最近讨论：{json.dumps(state.get("messages", [])[-8:], ensure_ascii=False)}
可用证据编号：{state.get("valid_evidence_ids", [])}

请用简体中文发言，像战术室群聊。
仅输出 JSON：{{"msg_type":"STATEMENT|CHALLENGE|REBUTTAL|SUPPORT","content":"正文","refs":[],"evidence_ids":[]}}
- 引用事实必须带 evidence_ids
- CHALLENGE/REBUTTAL/SUPPORT 须在 refs 填论点编号如 E-001
"""
    data = await call_llm_json(prompt)
    return {
        "role": role,
        "msg_type": data.get("msg_type", "STATEMENT"),
        "content": data.get("content", ""),
        "refs": data.get("refs", []),
        "evidence_ids": data.get("evidence_ids", []),
    }


async def specialist_node(state: WarRoomState) -> dict[str, Any]:
    role = state.get("next_role")
    if role not in SPECIALIST_ROLES:
        return {"error": f"invalid next_role: {role}"}

    tool_result = await _run_tools(role, state["match_id"])
    msg = await _generate_with_tools(role, state, tool_result)

    if state.get("mode") == "followup":
        user_q = state.get("user_reply") or ""
        if user_q and not msg.get("content"):
            msg["content"] = f"针对你的问题：{user_q}"

    msg["role"] = role
    msg["phase"] = state.get("phase", "Analysis")

    valid = set(state.get("valid_evidence_ids", []))
    result = validate_message(
        msg,
        phase=state.get("phase", "Analysis"),
        valid_evidence_ids=valid,
    )
    if not result.ok:
        msg = {
            **msg,
            "msg_type": "REVISE",
            "content": f"（修订）{msg.get('content', '')}",
        }

    messages = list(state.get("messages", []))
    claim_idx = len(state.get("claims_registry", {}))
    if msg.get("msg_type") == "STATEMENT" and msg.get("content"):
        claim_idx += 1
        msg["claim_id"] = f"E-{claim_idx:03d}"

    messages.append(msg)
    registry = dict(state.get("claims_registry", {}))
    if msg.get("claim_id"):
        registry[msg["claim_id"]] = msg.get("content", "")[:120]

    outputs = dict(state.get("specialist_outputs", {}))
    outputs[role] = {"tool_result": tool_result, "summary": msg.get("content", "")[:500]}

    return {
        "messages": messages,
        "claims_registry": registry,
        "specialist_outputs": outputs,
        "turn": state.get("turn", 0) + 1,
        "next_role": None,
    }
