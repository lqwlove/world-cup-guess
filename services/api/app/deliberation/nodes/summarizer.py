"""Summarizer agent: produce consensus artifact and final message."""

import json
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.deliberation.activity import publish_agent_analyzing, publish_agent_idle
from app.deliberation.constants import SUPERVISOR_ROLE
from app.deliberation.llm import call_llm_json
from app.deliberation.rules import count_votes, median_confidence
from app.deliberation.state import WarRoomState
from app.services.market_service import compute_market_edge

settings = get_settings()


def _build_artifact(state: WarRoomState) -> dict[str, Any]:
    votes = state.get("votes_1x2", [])
    vote_result = count_votes(votes)
    conf, band = median_confidence(votes)

    market = state.get("market_snapshot", {})
    consensus_probs = {
        "home": conf if vote_result.get("pick") == "home" else max(0.1, 1 - conf - 0.25),
        "draw": 0.24,
        "away": 0.18,
    }
    if vote_result.get("pick") == "away":
        consensus_probs = {"home": 0.2, "draw": 0.25, "away": conf}
    elif vote_result.get("pick") == "draw":
        consensus_probs = {"home": 0.3, "draw": conf, "away": 0.25}

    market_edge = compute_market_edge(consensus_probs, market) if market else []
    strength = vote_result.get("strength", "weak")
    pick = vote_result.get("pick", "home") if strength != "abstain" else "home"
    if strength == "abstain":
        conf = 0.5

    reasons = list(state.get("claims_registry", {}).keys())[:2] or ["E-001"]
    registry = state.get("claims_registry", {})

    return {
        "match_id": state["match_id"],
        "status": "CONSENSUS_FINAL",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "consensus_strength": strength if strength != "abstain" else "weak",
        "plays": {
            "1x2": {
                "pick": pick,
                "confidence": round(conf, 2),
                "confidence_band": [round(band[0], 2), round(band[1], 2)],
                "reasons": reasons,
                "dissent": "分裂共识" if strength == "weak" else None,
            },
            "score_top3": [
                {"score": "2-1", "confidence": 0.17},
                {"score": "1-1", "confidence": 0.14},
                {"score": "1-0", "confidence": 0.11},
            ],
            "handicap": {
                "line": "-0.5",
                "pick": pick,
                "confidence": round(conf - 0.04, 2),
                "abstain": strength == "abstain",
            },
        },
        "market_edge": market_edge,
        "minority_opinions": [
            {
                "role": "skeptic",
                "summary": registry.get(reasons[0], "赛果方差仍偏高。")[:80],
            }
        ],
        "unresolved": state.get("unresolved", []),
        "skeptic_ack": state.get("skeptic_ack", "ACK_WITH_RESERVATION"),
    }


async def summarizer_node(state: WarRoomState) -> dict[str, Any]:
    messages = list(state.get("messages", []))
    home = state.get("match_context", {}).get("home_team", "")
    away = state.get("match_context", {}).get("away_team", "")
    discussion_id = state.get("discussion_id", "")
    if discussion_id:
        await publish_agent_analyzing(discussion_id, "summarizer")

    if settings.mock_llm:
        summary_text = (
            f"合议总结：{home} vs {away}。综合数据、阵容与市场信息，"
            f"建议关注主胜方向，比分参考 2-1 / 1-1。风控保留意见：冷门方差仍存。"
        )
    else:
        prompt = f"""你是总结官。根据以下战术室讨论输出简体中文合议摘要（200字内）：
{json.dumps(messages[-24:], ensure_ascii=False)}

要求：
- 保留各方鲜明分歧，不要抹平成「双方差不多」
- 写清主流观点、反对派质疑、最终倾向（主胜/平/客胜）及比分参考
- 若存在未化解争议，在摘要中点明

仅输出 JSON：{{"summary":"正文","skeptic_ack":"ACK|ACK_WITH_RESERVATION"}}
"""
        data = await call_llm_json(prompt)
        summary_text = data.get("summary", "合议已完成。")
        state = {**state, "skeptic_ack": data.get("skeptic_ack", "ACK_WITH_RESERVATION")}

    artifact = _build_artifact(state)
    final_msg = {
        "role": "summarizer",
        "msg_type": "CONSENSUS_FINAL",
        "content": summary_text,
        "refs": [],
        "evidence_ids": [],
        "phase": "Summary",
    }
    messages.append(final_msg)

    supervisor_note = {
        "role": SUPERVISOR_ROLE,
        "msg_type": "STATEMENT",
        "content": "调度官：分析完成，已生成共识结论。你可继续追问各专家。",
        "refs": [],
        "evidence_ids": [],
        "phase": "Summary",
    }
    messages.append(supervisor_note)

    if discussion_id:
        await publish_agent_idle(discussion_id, "summarizer")

    return {
        "messages": messages,
        "final_artifact": artifact,
        "status": "completed",
        "phase": "Summary",
        "skeptic_ack": state.get("skeptic_ack", "ACK_WITH_RESERVATION"),
    }
