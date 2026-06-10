"""Summarizer agent: produce consensus artifact and final message."""

import json
from datetime import datetime
from typing import Any

from app.config import get_settings
from app.deliberation.activity import publish_agent_analyzing, publish_agent_idle
from app.deliberation.constants import SUPERVISOR_ROLE
from app.deliberation.debate_analysis import extract_votes_from_messages, score_top3_from_messages
from app.deliberation.debate_schedule import build_disagreement_matrix
from app.deliberation.llm import call_llm_json
from app.deliberation.rules import count_votes, median_confidence
from app.deliberation.state import WarRoomState
from app.services.market_service import compute_market_edge

settings = get_settings()


def _build_artifact(state: WarRoomState) -> dict[str, Any]:
    messages = state.get("messages", [])
    votes = state.get("votes_1x2") or extract_votes_from_messages(messages)
    vote_result = count_votes(votes)
    conf, band = median_confidence(votes)

    market = state.get("market_snapshot", {})
    pick = vote_result.get("pick") or "home"
    strength = vote_result.get("strength", "weak")

    if strength == "abstain" or not votes:
        conf = 0.5
        consensus_probs = {"home": 0.34, "draw": 0.33, "away": 0.33}
        pick = max(consensus_probs, key=consensus_probs.get)
    else:
        consensus_probs = {k: 0.12 for k in ("home", "draw", "away")}
        consensus_probs[pick] = max(conf, 0.38)
        rest = 1.0 - consensus_probs[pick]
        others = [k for k in consensus_probs if k != pick]
        for k in others:
            consensus_probs[k] = rest / len(others)

    market_edge = compute_market_edge(consensus_probs, market) if market else []
    if strength == "abstain":
        pick = vote_result.get("pick") or pick

    reasons = list(state.get("claims_registry", {}).keys())[:2] or ["E-001"]
    registry = state.get("claims_registry", {})

    total_prob = sum(consensus_probs.values()) or 1.0
    probs_pct = {
        k: int(round(v / total_prob * 100)) for k, v in consensus_probs.items()
    }
    diff = 100 - sum(probs_pct.values())
    if diff:
        top_key = max(probs_pct, key=probs_pct.get)
        probs_pct[top_key] += diff
    result_pick = max(probs_pct, key=probs_pct.get)
    score_top3 = score_top3_from_messages(messages)
    top_score = max(score_top3, key=lambda s: s["confidence"])["score"]

    matrix = build_disagreement_matrix(
        messages,
        registry,
        state.get("claim_authors", {}),
        state.get("unresolved", []),
    )

    minority = []
    for v in votes:
        if v.get("pick") and v.get("pick") != pick:
            minority.append(
                {
                    "role": v.get("role", ""),
                    "summary": f"倾向{'主胜' if v['pick']=='home' else '平局' if v['pick']=='draw' else '客胜'}",
                }
            )

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
                "dissent": "分裂共识" if strength == "weak" or minority else None,
            },
            "score_top3": score_top3,
            "handicap": {
                "line": "-0.5",
                "pick": pick,
                "confidence": round(conf - 0.04, 2),
                "abstain": strength == "abstain",
            },
        },
        "market_edge": market_edge,
        "minority_opinions": minority[:3] or [
            {
                "role": "skeptic",
                "summary": registry.get(reasons[0], "赛果方差仍偏高。")[:80],
            }
        ],
        "unresolved": state.get("unresolved", []),
        "disagreement_matrix": matrix,
        "skeptic_ack": state.get("skeptic_ack", "ACK_WITH_RESERVATION"),
        "prediction": {
            "pick": result_pick,
            "probs": probs_pct,
            "score": top_score,
        },
    }


async def summarizer_node(state: WarRoomState) -> dict[str, Any]:
    messages = list(state.get("messages", []))
    home = state.get("match_context", {}).get("home_team", "")
    away = state.get("match_context", {}).get("away_team", "")
    discussion_id = state.get("discussion_id", "")
    if discussion_id:
        await publish_agent_analyzing(discussion_id, "summarizer")

    matrix = build_disagreement_matrix(
        messages,
        state.get("claims_registry", {}),
        state.get("claim_authors", {}),
        state.get("unresolved", []),
    )

    if settings.mock_llm:
        summary_text = (
            f"合议总结：{home} vs {away}。经开场、交叉质询与情景推演，"
            f"主流倾向主胜，比分参考 {max(score_top3_from_messages(messages), key=lambda s: s['confidence'])['score']}。"
            f"风控对冷门剧本保留意见。"
        )
    else:
        prompt = f"""你是总结官。根据以下战术室讨论输出简体中文合议摘要（220字内）：
{json.dumps(messages[-28:], ensure_ascii=False)}

分歧矩阵：
{json.dumps(matrix, ensure_ascii=False)}

要求：
- 保留各方鲜明分歧，不要抹平成「双方差不多」
- 写清主流观点、反对派质疑、情景推演中的冷门剧本、最终倾向（主胜/平/客胜）及比分参考
- 若存在未化解争议（unresolved），在摘要中点明

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
        "votes_1x2": extract_votes_from_messages(messages),
    }
