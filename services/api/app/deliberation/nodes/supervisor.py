"""Supervisor node: routes next specialist, asks user, or finishes analysis."""

import json
from typing import Any

from app.config import get_settings
from app.deliberation.constants import ROLE_LABELS, SPECIALIST_ROLES, SUPERVISOR_ROLE
from app.deliberation.debate_schedule import (
    PHASE_BRAINSTORM,
    PHASE_CROSS,
    PHASE_OPENING,
    PHASE_RECONCILE,
    PHASE_SUMMARY,
    detect_phase,
    pick_next_role,
)
from app.deliberation.llm import call_llm_json
from app.deliberation.state import WarRoomState

settings = get_settings()


def _roles_spoken(messages: list[dict[str, Any]]) -> set[str]:
    return {
        m["role"]
        for m in messages
        if m.get("role") in SPECIALIST_ROLES and m.get("msg_type") not in ("TOOL_CALL",)
    }


def _mock_supervisor(state: WarRoomState) -> dict[str, Any]:
    mode = state.get("mode", "analysis")
    messages = state.get("messages", [])
    claim_authors = state.get("claim_authors", {})
    unresolved = state.get("unresolved", [])

    if mode == "followup":
        reply = (state.get("user_reply") or "").strip()
        role = _route_followup(reply)
        return {
            "supervisor_action": "call_agent",
            "next_role": role,
            "supervisor_reason": f"会后追问，路由至{ROLE_LABELS.get(role, role)}",
            "pending_user_question": None,
            "awaiting_user": False,
            "user_reply": None,
            "phase": "FollowUp",
        }

    if state.get("turn", 0) >= state.get("max_turns", settings.max_rounds):
        return _finish_decision("已达最大轮次，进入总结")

    next_role, phase, reason = pick_next_role(messages, claim_authors, unresolved)
    if next_role is None:
        return _finish_decision(reason)

    return {
        "supervisor_action": "call_agent",
        "next_role": next_role,
        "supervisor_reason": reason,
        "pending_user_question": None,
        "awaiting_user": False,
        "phase": phase,
    }


def _route_followup(text: str) -> str:
    if any(k in text for k in ("让球", "盘口", "handicap")):
        return "handicap"
    if any(k in text for k in ("比分", "进球", "score")):
        return "scoreline"
    if any(k in text for k in ("市场", "赔率", "polymarket", "概率")):
        return "market"
    if any(k in text for k in ("阵容", "伤病", "球员")):
        return "squad"
    if any(k in text for k in ("质疑", "风险", "冷门")):
        return "skeptic"
    if any(k in text for k in ("数据", "战绩", "交锋")):
        return "data"
    return "data"


async def _llm_supervisor(state: WarRoomState) -> dict[str, Any]:
    home = state.get("match_context", {}).get("home_team", "")
    away = state.get("match_context", {}).get("away_team", "")
    messages = state.get("messages", [])
    mode = state.get("mode", "analysis")
    phase = detect_phase(messages)
    unresolved = state.get("unresolved", [])

    prompt = f"""你是世界杯 AI 战术室【调度官】（supervisor），负责决定下一步行动。
对阵：{home} vs {away}
模式：{mode}
当前阶段：{phase}
当前轮次：{state.get("turn", 0)} / {state.get("max_turns", settings.max_rounds)}
未决议题：{unresolved or "无"}
已发言专家：{sorted(_roles_spoken(messages))}
可选专家：{SPECIALIST_ROLES}
最近消息：{json.dumps(messages[-8:], ensure_ascii=False)}

仅输出 JSON：
{{"action":"call_agent|ask_user|finish","next_role":"data|squad|market|skeptic|handicap|scoreline|null","reason":"中文简短理由","user_question":"仅 ask_user 时填写"}}

规则：
- analysis 模式分四段：开场 → 交叉质询 → 情景推演(Brainstorm) → 清账(Reconcile)
- 有 CHALLENGE 未回应时，优先召回被质疑论点作者
- 未决议题未清账前不要 finish
- followup 模式：根据用户问题路由到最相关专家
"""
    data = await call_llm_json(prompt)
    action = data.get("action", "call_agent")
    if action not in ("call_agent", "ask_user", "finish", "partial"):
        action = "call_agent"
    next_role = data.get("next_role")
    if action == "call_agent" and next_role not in SPECIALIST_ROLES:
        next_role = _route_followup(state.get("user_reply") or "")
    return {
        "supervisor_action": action,
        "next_role": next_role if action == "call_agent" else None,
        "supervisor_reason": data.get("reason", ""),
        "pending_user_question": data.get("user_question") if action == "ask_user" else None,
        "awaiting_user": action == "ask_user",
        "user_reply": None if mode == "followup" else state.get("user_reply"),
    }


def _finish_decision(reason: str) -> dict[str, Any]:
    return {
        "supervisor_action": "finish",
        "next_role": None,
        "supervisor_reason": reason,
        "pending_user_question": None,
        "awaiting_user": False,
        "phase": PHASE_SUMMARY,
    }


def _apply_analysis_schedule(state: WarRoomState, decision: dict[str, Any]) -> dict[str, Any]:
    """分析模式：调度表 + 动态召回，防止 LLM 过早 finish。"""
    if state.get("mode") != "analysis":
        return decision

    if decision.get("supervisor_action") == "ask_user":
        return decision

    if state.get("turn", 0) >= state.get("max_turns", settings.max_rounds):
        return _finish_decision("已达最大轮次，进入总结")

    messages = state.get("messages", [])
    claim_authors = state.get("claim_authors", {})
    unresolved = state.get("unresolved", [])

    next_role, phase, reason = pick_next_role(messages, claim_authors, unresolved)
    if next_role is None:
        return _finish_decision(reason)

    return {
        "supervisor_action": "call_agent",
        "next_role": next_role,
        "supervisor_reason": reason,
        "pending_user_question": None,
        "awaiting_user": False,
        "phase": phase,
    }


async def supervisor_node(state: WarRoomState) -> dict[str, Any]:
    if settings.mock_llm:
        decision = _mock_supervisor(state)
    else:
        decision = await _llm_supervisor(state)
        decision = _apply_analysis_schedule(state, decision)

    trace = list(state.get("supervisor_trace", []))
    trace.append(
        {
            "turn": state.get("turn", 0),
            "action": decision["supervisor_action"],
            "next_role": decision.get("next_role"),
            "reason": decision.get("supervisor_reason", ""),
            "phase": decision.get("phase", state.get("phase")),
        }
    )

    updates: dict[str, Any] = {
        **decision,
        "supervisor_trace": trace,
        "resume_to_supervisor": False,
    }
    if decision.get("phase"):
        updates["phase"] = decision["phase"]

    if decision["supervisor_action"] == "ask_user":
        question = decision.get("pending_user_question") or "请补充你的关注点。"
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": SUPERVISOR_ROLE,
                "msg_type": "SYSTEM_QUESTION",
                "content": question,
                "refs": [],
                "evidence_ids": [],
                "phase": updates.get("phase", state.get("phase", PHASE_OPENING)),
            }
        )
        updates["messages"] = messages
        updates["status"] = "awaiting_user"

    return updates
