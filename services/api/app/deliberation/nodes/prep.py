"""Initialize war room state for a discussion run."""

from typing import Any

from sqlalchemy import select

from app.deliberation.match_brief import build_match_context
from app.deliberation.runtime import get_session
from app.deliberation.state import WarRoomState
from app.models.entities import Match, MatchFact
from app.services.market_service import fetch_polymarket_snapshot

async def prep_node(state: WarRoomState) -> dict[str, Any]:
    session = get_session()
    match = await session.get(Match, state["match_id"])
    if not match:
        return {"status": "failed", "error": "match not found"}

    result = await session.execute(select(MatchFact).where(MatchFact.match_id == state["match_id"]))
    valid_evidence_ids = [f.evidence_id for f in result.scalars().all()]
    snap = await fetch_polymarket_snapshot(session, state["match_id"])
    market_probs = snap.probabilities if snap else {}

    match_context = build_match_context(match)
    match_context["market_snapshot"] = market_probs
    match_context["market_available"] = bool(market_probs)

    updates: dict[str, Any] = {
        "match_context": match_context,
        "valid_evidence_ids": valid_evidence_ids,
        "market_snapshot": market_probs,
        "status": "running",
        "phase": "Analysis" if state.get("mode", "analysis") == "analysis" else "FollowUp",
        "turn": state.get("turn", 0),
        "claims_registry": state.get("claims_registry") or {},
        "specialist_outputs": state.get("specialist_outputs") or {},
        "supervisor_trace": state.get("supervisor_trace") or [],
        "unresolved": state.get("unresolved") or [],
        "persisted_count": state.get("persisted_count", 0),
        "awaiting_user": False,
    }

    if state.get("mode", "analysis") == "analysis" and not state.get("messages"):
        updates["messages"] = []

    return updates
