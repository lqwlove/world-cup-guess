"""Tests for debate scheduling."""

from app.deliberation.debate_schedule import (
    PHASE_BRAINSTORM,
    PHASE_CROSS,
    PHASE_OPENING,
    PHASE_RECONCILE,
    detect_phase,
    pick_next_role,
    update_unresolved,
)


def _msg(role: str, msg_type: str = "STATEMENT", refs=None):
    return {"role": role, "msg_type": msg_type, "refs": refs or [], "content": "x"}


def test_phase_progression():
    messages = []
    assert detect_phase(messages) == PHASE_OPENING
    for role in ["data", "squad", "market", "skeptic", "handicap", "scoreline"]:
        messages.append(_msg(role))
    assert detect_phase(messages) == PHASE_CROSS


def test_unresolved_tracking():
    u = update_unresolved([], _msg("skeptic", "CHALLENGE", ["E-001"]))
    assert "E-001" in u
    u = update_unresolved(u, _msg("data", "REBUTTAL", ["E-001"]))
    assert "E-001" not in u


def test_dynamic_recall_on_challenge():
    messages = [_msg("data"), _msg("skeptic", "CHALLENGE", ["E-001"])]
    authors = {"E-001": "data"}
    role, phase, _ = pick_next_role(messages, authors, ["E-001"])
    assert role == "data"
    assert phase in (PHASE_CROSS, PHASE_RECONCILE)
