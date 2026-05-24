"""LLM adapter with mock mode for development."""

import json
from typing import Any

from app.config import get_settings
from app.deliberation.constants import ROLE_LABELS

settings = get_settings()


async def generate_role_message(
    *,
    role: str,
    phase: str,
    match_context: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    valid_evidence_ids: list[str],
) -> dict[str, Any]:
    if settings.mock_llm:
        return _mock_message(role, phase, match_context, valid_evidence_ids)

    prompt = _build_prompt(role, phase, match_context, recent_messages, valid_evidence_ids)
    raw = await _call_llm(prompt)
    try:
        data = json.loads(raw)
        return {
            "role": role,
            "msg_type": data.get("msg_type", "STATEMENT"),
            "content": data.get("content", ""),
            "refs": data.get("refs", []),
            "evidence_ids": data.get("evidence_ids", []),
        }
    except json.JSONDecodeError:
        return {
            "role": role,
            "msg_type": "STATEMENT",
            "content": raw[:500],
            "refs": [],
            "evidence_ids": [],
        }


def _mock_message(
    role: str,
    phase: str,
    match_context: dict[str, Any],
    valid_evidence_ids: list[str],
) -> dict[str, Any]:
    home = match_context.get("home_team", "Home")
    away = match_context.get("away_team", "Away")
    ev = valid_evidence_ids[0] if valid_evidence_ids else "EV-demo-001"

    templates = {
        "data": ("STATEMENT", f"{home} recent form supports slight edge per {ev}.", [ev]),
        "squad": ("STATEMENT", f"Key players for {home} vs {away} appear fit.", [ev] if valid_evidence_ids else []),
        "market": ("STATEMENT", "Market prices home near 48%; watch for drift.", []),
        "skeptic": ("CHALLENGE", f"@data Counter-attack risk for {away} may be understated.", ["E-001"]),
        "handicap": ("STATEMENT", "Home -0.5 line looks fair given form.", []),
        "scoreline": ("STATEMENT", "Top scores cluster 2-1, 1-1, 1-0.", []),
        "moderator": ("STATEMENT", f"Phase {phase}: proceeding with deliberation.", []),
    }

    if phase == "FinalVote" and role != "moderator":
        return {
            "role": role,
            "msg_type": "VOTE",
            "content": json.dumps({"pick": "home", "p_low": 0.52, "p_high": 0.62}),
            "refs": [],
            "evidence_ids": [],
        }

    if phase == "Consensus" and role == "moderator":
        return {
            "role": role,
            "msg_type": "CONSENSUS_FINAL",
            "content": "Consensus document finalized.",
            "refs": [],
            "evidence_ids": [],
        }

    if phase == "Consensus" and role == "skeptic":
        return {
            "role": role,
            "msg_type": "ACK_WITH_RESERVATION",
            "content": "Signed with reservation on variance.",
            "refs": [],
            "evidence_ids": [],
        }

    if phase == "CrossExam" and role == "skeptic":
        msg_type, content, evs = ("CHALLENGE", f"@data {away} efficiency questioned.", [])
        return {"role": role, "msg_type": msg_type, "content": content, "refs": ["E-001"], "evidence_ids": evs}

    if phase == "CrossExam" and role == "data":
        return {
            "role": role,
            "msg_type": "REBUTTAL",
            "content": f"E-001 addressed with {ev}.",
            "refs": ["E-001"],
            "evidence_ids": [ev],
        }

    msg_type, content, evs = templates.get(role, ("STATEMENT", "Noted.", []))
    return {"role": role, "msg_type": msg_type, "content": content, "refs": [], "evidence_ids": evs}


def _build_prompt(
    role: str,
    phase: str,
    match_context: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    valid_evidence_ids: list[str],
) -> str:
    label = ROLE_LABELS.get(role, role)
    return f"""You are the {label} ({role}) in an AI tactical room.
Phase: {phase}
Match: {match_context.get('home_team')} vs {match_context.get('away_team')}
Valid evidence IDs: {valid_evidence_ids}
Recent messages: {json.dumps(recent_messages[-5:], ensure_ascii=False)}
Respond ONLY with JSON: {{"msg_type":"...","content":"...","refs":[],"evidence_ids":[]}}
Rules: factual STATEMENTs need evidence_ids; CHALLENGE/SUPPORT need refs.
"""


async def _call_llm(prompt: str) -> str:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        llm = ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        return resp.content

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        return resp.content

    return json.dumps({"msg_type": "STATEMENT", "content": "LLM unavailable.", "refs": [], "evidence_ids": []})
