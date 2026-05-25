"""LangGraph deliberation state machine."""

from datetime import datetime
from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.config import get_settings
from app.deliberation.constants import PHASES, ROLES
from app.deliberation.llm import generate_role_message
from app.deliberation.rules import count_votes, median_confidence, validate_message
from app.deliberation.state import DeliberationState
from app.services.market_service import compute_market_edge

settings = get_settings()


def build_deliberation_graph() -> Any:
    graph = StateGraph(DeliberationState)

    graph.add_node("opening", _opening_node)
    graph.add_node("cross_exam", _cross_exam_node)
    graph.add_node("deep_dive", _deep_dive_node)
    graph.add_node("playbook_split", _playbook_split_node)
    graph.add_node("final_vote", _final_vote_node)
    graph.add_node("consensus", _consensus_node)
    graph.add_node("partial_end", _partial_end_node)

    graph.set_entry_point("opening")
    graph.add_conditional_edges("opening", _after_opening, {"cross_exam": "cross_exam", "partial": "partial_end"})
    graph.add_conditional_edges("cross_exam", _after_cross_exam, {"cross_exam": "cross_exam", "deep_dive": "deep_dive", "partial": "partial_end"})
    graph.add_conditional_edges("deep_dive", _after_deep_dive, {"deep_dive": "deep_dive", "playbook": "playbook_split", "partial": "partial_end"})
    graph.add_conditional_edges("playbook_split", _after_playbook, {"final_vote": "final_vote", "partial": "partial_end"})
    graph.add_edge("partial_end", END)
    graph.add_edge("final_vote", "consensus")
    graph.add_conditional_edges("consensus", _after_consensus, {"done": END, "partial": END})

    return graph.compile()


def _max_rounds(state: DeliberationState) -> int:
    return state.get("max_rounds", settings.max_rounds)


def _increment_round(state: DeliberationState) -> DeliberationState:
    return {**state, "round": state.get("round", 0) + 1}


def _is_partial(state: DeliberationState) -> bool:
    return state.get("round", 0) >= _max_rounds(state)


async def _opening_node(state: DeliberationState) -> DeliberationState:
    state = {**state, "phase": "Opening", "opening_done": False}
    messages = list(state.get("messages", []))
    claim_idx = len(state.get("claims_registry", {}))

    for role in ROLES:
        if role == "moderator":
            continue
        msg = await generate_role_message(
            role=role,
            phase="Opening",
            match_context=state["match_context"],
            recent_messages=messages,
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )
        msg, claim_idx = _apply_message(state, msg, claim_idx)
        messages.append(msg)

    mod_msg = await generate_role_message(
        role="moderator",
        phase="Opening",
        match_context=state["match_context"],
        recent_messages=messages,
        valid_evidence_ids=state.get("valid_evidence_ids", []),
    )
    mod_msg, claim_idx = _apply_message(state, mod_msg, claim_idx)
    messages.append(mod_msg)

    return _increment_round({**state, "messages": messages, "opening_done": True, "claims_registry": _registry(messages)})


async def _cross_exam_node(state: DeliberationState) -> DeliberationState:
    state = {**state, "phase": "CrossExam"}
    messages = list(state.get("messages", []))
    claim_idx = len(state.get("claims_registry", {}))
    had_challenge = False

    for role in ["skeptic", "data", "market", "moderator"]:
        msg = await generate_role_message(
            role=role,
            phase="CrossExam",
            match_context=state["match_context"],
            recent_messages=messages,
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )
        msg, claim_idx = _apply_message(state, msg, claim_idx)
        messages.append(msg)
        if msg["msg_type"] == "CHALLENGE":
            had_challenge = True

    challenge_streak = 0 if had_challenge else state.get("challenge_streak", 0) + 1
    cross_rounds = state.get("cross_exam_rounds", 0) + 1

    return _increment_round(
        {
            **state,
            "messages": messages,
            "challenge_streak": challenge_streak,
            "cross_exam_rounds": cross_rounds,
            "last_challenge_round": state.get("round", 0) if had_challenge else state.get("last_challenge_round", 0),
            "claims_registry": _registry(messages),
        }
    )


async def _deep_dive_node(state: DeliberationState) -> DeliberationState:
    state = {**state, "phase": "DeepDive"}
    messages = list(state.get("messages", []))
    claim_idx = len(state.get("claims_registry", {}))
    had_challenge = False

    for role in ["handicap", "scoreline", "skeptic", "data"]:
        msg = await generate_role_message(
            role=role,
            phase="DeepDive",
            match_context=state["match_context"],
            recent_messages=messages,
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )
        msg, claim_idx = _apply_message(state, msg, claim_idx)
        messages.append(msg)
        if msg["msg_type"] == "CHALLENGE":
            had_challenge = True

    challenge_streak = 0 if had_challenge else state.get("challenge_streak", 0) + 1

    if state.get("round", 0) % 5 == 0:
        digest = {
            "role": "moderator",
            "msg_type": "THREAD_DIGEST",
            "content": f"第 {state.get('round')} 轮摘要：近况优势与反击风险仍是分歧焦点。",
            "refs": [],
            "evidence_ids": [],
            "phase": "DeepDive",
        }
        messages.append(digest)

    return _increment_round(
        {**state, "messages": messages, "challenge_streak": challenge_streak, "claims_registry": _registry(messages)}
    )


async def _playbook_split_node(state: DeliberationState) -> DeliberationState:
    state = {**state, "phase": "PlaybookSplit"}
    messages = list(state.get("messages", []))
    claim_idx = len(state.get("claims_registry", {}))

    for role in ["handicap", "scoreline", "market", "moderator"]:
        msg = await generate_role_message(
            role=role,
            phase="PlaybookSplit",
            match_context=state["match_context"],
            recent_messages=messages,
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )
        msg, claim_idx = _apply_message(state, msg, claim_idx)
        messages.append(msg)

    return _increment_round({**state, "messages": messages, "playbook_done": True, "claims_registry": _registry(messages)})


async def _final_vote_node(state: DeliberationState) -> DeliberationState:
    state = {**state, "phase": "FinalVote", "vote_open": True}
    messages = list(state.get("messages", []))
    votes: list[dict[str, Any]] = []

    mod_open = {
        "role": "moderator",
        "msg_type": "STATEMENT",
        "content": "Final vote opened for 1x2.",
        "refs": [],
        "evidence_ids": [],
        "phase": "FinalVote",
    }
    messages.append(mod_open)

    for role in ROLES:
        if role in ("moderator",):
            continue
        msg = await generate_role_message(
            role=role,
            phase="FinalVote",
            match_context=state["match_context"],
            recent_messages=messages,
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )
        result = validate_message(
            msg,
            phase="FinalVote",
            valid_evidence_ids=set(state.get("valid_evidence_ids", [])),
            vote_open=True,
        )
        if result.ok and msg["msg_type"] == "VOTE":
            import json

            try:
                vote_data = json.loads(msg["content"])
            except json.JSONDecodeError:
                vote_data = {"pick": "home", "p_low": 0.5, "p_high": 0.6}
            votes.append({"role": role, **vote_data})
        msg["phase"] = "FinalVote"
        messages.append(msg)

    return _increment_round({**state, "messages": messages, "votes_1x2": votes})


async def _partial_end_node(state: DeliberationState) -> DeliberationState:
    artifact = _build_artifact(state, state.get("messages", []))
    artifact["status"] = "PARTIAL_CONSENSUS"
    artifact["consensus_strength"] = "partial"
    artifact["unresolved"] = artifact.get("unresolved", []) + [
        "未在 max_rounds 内达成全部共识条件"
    ]
    artifact["skeptic_ack"] = state.get("skeptic_ack") or "PENDING"
    return {
        **state,
        "final_artifact": artifact,
        "status": "PARTIAL_CONSENSUS",
        "phase": "Consensus",
    }


async def _consensus_node(state: DeliberationState) -> DeliberationState:
    state = {**state, "phase": "Consensus"}
    messages = list(state.get("messages", []))

    for role in ["moderator", "skeptic"]:
        msg = await generate_role_message(
            role=role,
            phase="Consensus",
            match_context=state["match_context"],
            recent_messages=messages,
            valid_evidence_ids=state.get("valid_evidence_ids", []),
        )
        msg["phase"] = "Consensus"
        messages.append(msg)
        if role == "skeptic" and msg["msg_type"] in ("ACK", "ACK_WITH_RESERVATION"):
            state = {**state, "skeptic_ack": msg["msg_type"]}

    artifact = _build_artifact(state, messages)
    status = "CONSENSUS_FINAL" if state.get("skeptic_ack") and artifact else "PARTIAL_CONSENSUS"
    if state.get("unresolved"):
        status = "PARTIAL_CONSENSUS"
        artifact["status"] = status
        artifact["consensus_strength"] = "partial"

    return {
        **state,
        "messages": messages,
        "final_artifact": artifact,
        "status": status,
    }


def _build_artifact(state: DeliberationState, messages: list[dict]) -> dict[str, Any]:
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
    if strength == "abstain":
        pick = "home"
        conf = 0.5
    else:
        pick = vote_result.get("pick", "home")

    reasons = [k for k in state.get("claims_registry", {})][:2] or ["E-001"]

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
            {"role": "skeptic", "summary": "反击方差与冷门概率仍可能被低估。"}
        ],
        "unresolved": state.get("unresolved", []),
        "skeptic_ack": state.get("skeptic_ack", "ACK_WITH_RESERVATION"),
    }


def _apply_message(
    state: DeliberationState, msg: dict[str, Any], claim_idx: int
) -> tuple[dict[str, Any], int]:
    valid = set(state.get("valid_evidence_ids", []))
    retries = 0
    while retries < 2:
        result = validate_message(
            msg,
            phase=state.get("phase", "Opening"),
            valid_evidence_ids=valid,
            vote_open=state.get("vote_open", False),
        )
        if result.ok:
            break
        retries += 1
        msg = {**msg, "msg_type": "REVISE", "content": f"（修订）{msg.get('content', '')}"}

    if msg.get("msg_type") == "STATEMENT" and msg.get("content"):
        claim_idx += 1
        msg["claim_id"] = f"E-{claim_idx:03d}"

    msg["phase"] = state.get("phase", "Opening")
    return msg, claim_idx


def _registry(messages: list[dict]) -> dict[str, str]:
    reg = {}
    for m in messages:
        if m.get("claim_id"):
            reg[m["claim_id"]] = m.get("content", "")[:120]
    return reg


def _after_opening(state: DeliberationState) -> Literal["cross_exam", "partial"]:
    if _is_partial(state):
        return "partial"
    return "cross_exam"


def _after_cross_exam(state: DeliberationState) -> Literal["cross_exam", "deep_dive", "partial"]:
    if _is_partial(state):
        return "partial"
    if state.get("cross_exam_rounds", 0) < 2:
        return "cross_exam"
    return "deep_dive"


def _after_deep_dive(state: DeliberationState) -> Literal["deep_dive", "playbook", "partial"]:
    if _is_partial(state):
        return "partial"
    if state.get("challenge_streak", 0) >= 2:
        return "playbook"
    if state.get("round", 0) >= 8:
        return "playbook"
    return "deep_dive"


def _after_playbook(state: DeliberationState) -> Literal["final_vote", "partial"]:
    if _is_partial(state):
        return "partial"
    return "final_vote"


def _after_consensus(state: DeliberationState) -> Literal["done", "partial"]:
    return "done"
