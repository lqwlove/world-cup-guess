"""Supervisor node: routes next specialist, asks user, or finishes analysis."""

import json
from typing import Any

from app.config import get_settings
from app.deliberation.constants import ROLE_LABELS, SPECIALIST_ROLES, SUPERVISOR_ROLE
from app.deliberation.llm import call_llm_json
from app.deliberation.state import WarRoomState

settings = get_settings()

_OPENING_ORDER = ["data", "squad", "market", "skeptic", "handicap", "scoreline"]
# 首轮 6 人陈述后，再安排交叉质询（鼓励质疑与反驳）
_CROSS_EXAM_ORDER = ["skeptic", "market", "handicap", "scoreline"]
_ANALYSIS_ORDER = _OPENING_ORDER  # alias


def _role_speech_count(messages: list[dict[str, Any]], role: str) -> int:
    return sum(
        1
        for m in messages
        if m.get("role") == role and m.get("msg_type") not in ("TOOL_CALL",)
    )


def _pick_next_role(messages: list[dict[str, Any]]) -> str | None:
    for role in _OPENING_ORDER:
        if _role_speech_count(messages, role) < 1:
            return role
    for role in _CROSS_EXAM_ORDER:
        if _role_speech_count(messages, role) < 2:
            return role
    return None


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

    next_role = _pick_next_role(messages)
    if next_role:
        opening_done = all(_role_speech_count(messages, r) >= 1 for r in _OPENING_ORDER)
        phase_label = "交叉质询" if opening_done else "开场陈述"
        return {
            "supervisor_action": "call_agent",
            "next_role": next_role,
            "supervisor_reason": f"{phase_label}，请{ROLE_LABELS.get(next_role, next_role)}发言",
            "pending_user_question": None,
            "awaiting_user": False,
        }

    return {
        "supervisor_action": "finish",
        "next_role": None,
        "supervisor_reason": "陈述与交叉质询已完成，进入总结",
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
- analysis 模式：先让 data→squad→market→skeptic→handicap→scoreline 各开场陈述一次；
  然后安排 skeptic→market→handicap→scoreline 交叉质询第二轮（鼓励 CHALLENGE/REBUTTAL）
- 两轮都完成后再 finish；战术室需要观点碰撞，不要过早结束
- 仅当用户主动需要选择玩法方向时才 ask_user
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


def _finish_decision(reason: str) -> dict[str, Any]:
    return {
        "supervisor_action": "finish",
        "next_role": None,
        "supervisor_reason": reason,
        "pending_user_question": None,
        "awaiting_user": False,
    }


def _apply_analysis_schedule(state: WarRoomState, decision: dict[str, Any]) -> dict[str, Any]:
    """分析模式：按固定调度表推进，防止 LLM 调度官无限 call_agent。"""
    if state.get("mode") != "analysis":
        return decision

    messages = state.get("messages", [])
    turn = state.get("turn", 0)
    max_turns = state.get("max_turns", settings.max_rounds)

    if turn >= max_turns:
        return _finish_decision("已达最大轮次，进入总结")

    next_role = _pick_next_role(messages)
    if next_role is None:
        return _finish_decision("陈述与交叉质询已完成，进入总结")

    if decision.get("supervisor_action") == "ask_user":
        return decision

    opening_done = all(_role_speech_count(messages, r) >= 1 for r in _OPENING_ORDER)
    phase_label = "交叉质询" if opening_done else "开场陈述"
    return {
        "supervisor_action": "call_agent",
        "next_role": next_role,
        "supervisor_reason": f"{phase_label}，请{ROLE_LABELS.get(next_role, next_role)}发言",
        "pending_user_question": None,
        "awaiting_user": False,
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
        }
    )

    messages = state.get("messages", [])
    opening_done = all(_role_speech_count(messages, r) >= 1 for r in _OPENING_ORDER)
    if state.get("mode") == "followup":
        phase = "FollowUp"
    elif opening_done and decision.get("next_role") in _CROSS_EXAM_ORDER:
        phase = "CrossExam"
    else:
        phase = "Analysis"

    updates: dict[str, Any] = {
        **decision,
        "supervisor_trace": trace,
        "phase": phase,
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
