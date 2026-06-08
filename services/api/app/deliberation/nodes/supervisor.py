"""Supervisor node: routes next specialist, asks user, or finishes analysis."""

import json
from typing import Any

from app.config import get_settings
from app.deliberation.constants import ROLE_LABELS, SPECIALIST_ROLES, SUPERVISOR_ROLE
from app.deliberation.llm import call_llm_json
from app.deliberation.state import WarRoomState

settings = get_settings()

_ANALYSIS_ORDER = ["data", "squad", "market", "skeptic", "handicap", "scoreline"]


def _roles_spoken(messages: list[dict[str, Any]]) -> set[str]:
    return {m["role"] for m in messages if m.get("role") in SPECIALIST_ROLES}


def _user_answered_after_question(messages: list[dict[str, Any]]) -> bool:
    pending = False
    for m in messages:
        if m.get("msg_type") == "SYSTEM_QUESTION":
            pending = True
        if pending and m.get("role") == "user":
            return True
    return False


def _asked_user(messages: list[dict[str, Any]]) -> bool:
    return any(m.get("msg_type") == "SYSTEM_QUESTION" for m in messages)


def _mock_supervisor(state: WarRoomState) -> dict[str, Any]:
    mode = state.get("mode", "analysis")
    turn = state.get("turn", 0)
    max_turns = state.get("max_turns", settings.max_rounds)
    messages = state.get("messages", [])
    spoken = _roles_spoken(messages)

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
        }

    if turn >= max_turns:
        return {
            "supervisor_action": "finish",
            "next_role": None,
            "supervisor_reason": "已达最大轮次，进入总结",
            "pending_user_question": None,
            "awaiting_user": False,
        }

    missing = [r for r in _ANALYSIS_ORDER if r not in spoken]
    if missing:
        role = missing[0]
        return {
            "supervisor_action": "call_agent",
            "next_role": role,
            "supervisor_reason": f"首轮分析，请{ROLE_LABELS.get(role, role)}发言",
            "pending_user_question": None,
            "awaiting_user": False,
        }

    # 首轮 6 专家各发言一次后直接进入总结，不向用户索要玩法偏好
    return {
        "supervisor_action": "finish",
        "next_role": None,
        "supervisor_reason": "各专家已发言，进入总结",
        "pending_user_question": None,
        "awaiting_user": False,
    }


def _route_followup(text: str) -> str:
    t = text.lower()
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
    prompt = f"""你是世界杯 AI 战术室【调度官】（supervisor），负责决定下一步行动。
对阵：{home} vs {away}
模式：{mode}
当前轮次：{state.get("turn", 0)} / {state.get("max_turns", settings.max_rounds)}
已发言专家：{sorted(_roles_spoken(messages))}
可选专家：{SPECIALIST_ROLES}
最近消息：{json.dumps(messages[-6:], ensure_ascii=False)}
用户最新回复：{state.get("user_reply") or "无"}

仅输出 JSON：
{{"action":"call_agent|ask_user|finish","next_role":"data|squad|market|skeptic|handicap|scoreline|null","reason":"中文简短理由","user_question":"仅 ask_user 时填写"}}

规则：
- 这是 2026 世界杯正赛，禁止因「缺少赛事属性/名单」反复调度同一专家
- analysis 模式：优先让未发言的专家各陈述一次；6 人都发言后优先 finish
- 仅当用户主动需要选择玩法方向时才 ask_user，勿为索要基础赛况问用户
- 勿连续两轮调度同一专家，除非回应具体质疑
- followup 模式：根据用户问题路由到最相关专家（next_role 必填）
- finish 时 next_role 为 null
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


async def supervisor_node(state: WarRoomState) -> dict[str, Any]:
    if settings.mock_llm:
        decision = _mock_supervisor(state)
    else:
        decision = await _llm_supervisor(state)

    trace = list(state.get("supervisor_trace", []))
    trace.append(
        {
            "turn": state.get("turn", 0),
            "action": decision["supervisor_action"],
            "next_role": decision.get("next_role"),
            "reason": decision.get("supervisor_reason", ""),
        }
    )

    updates: dict[str, Any] = {
        **decision,
        "supervisor_trace": trace,
        "phase": "FollowUp" if state.get("mode") == "followup" else "Analysis",
        "resume_to_supervisor": False,
    }

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
                "phase": updates["phase"],
            }
        )
        updates["messages"] = messages
        updates["status"] = "awaiting_user"

    return updates
