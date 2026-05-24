"""Rule engine for discussion message validation."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RuleResult:
    ok: bool
    error: Optional[str] = None


def validate_message(
    msg: dict[str, Any],
    *,
    phase: str,
    valid_evidence_ids: set[str],
    vote_open: bool = False,
) -> RuleResult:
    msg_type = msg.get("msg_type", "")
    content = msg.get("content", "")
    evidence_ids = msg.get("evidence_ids") or []
    refs = msg.get("refs") or []

    if not content.strip():
        return RuleResult(False, "content is required")

    if msg_type == "STATEMENT" and _has_factual_claim(content):
        if not evidence_ids:
            return RuleResult(False, "STATEMENT with factual claims requires evidence_ids")
        missing = [e for e in evidence_ids if e not in valid_evidence_ids]
        if missing:
            return RuleResult(False, f"unknown evidence_ids: {missing}")

    if msg_type in ("CHALLENGE", "SUPPORT", "REBUTTAL"):
        if not refs:
            return RuleResult(False, f"{msg_type} requires refs to claim ids")

    if msg_type == "VOTE":
        if phase != "FinalVote":
            return RuleResult(False, "VOTE only allowed in FinalVote phase")
        if not vote_open:
            return RuleResult(False, "VOTE before moderator opened voting")

    if msg_type in ("ACK", "ACK_WITH_RESERVATION"):
        if msg.get("role") != "skeptic":
            return RuleResult(False, "only skeptic can ACK")

    return RuleResult(True)


def _has_factual_claim(content: str) -> bool:
    markers = ["EV-", "胜", "负", "进球", "战绩", "Elo", "elo", "W", "L", "D"]
    return any(m in content for m in markers)


def count_votes(votes: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate votes: 5/7 strong, 4/7 weak, else abstain."""
    if not votes:
        return {"strength": "abstain", "pick": None, "count": 0}

    picks: dict[str, int] = {}
    for v in votes:
        pick = v.get("pick")
        if pick:
            picks[pick] = picks.get(pick, 0) + 1

    if not picks:
        return {"strength": "abstain", "pick": None, "count": 0}

    top_pick = max(picks, key=picks.get)
    count = picks[top_pick]
    total = len(votes)

    if count >= 5:
        strength = "strong"
    elif count >= 4:
        strength = "weak"
    else:
        strength = "abstain"

    return {"strength": strength, "pick": top_pick, "count": count, "total": total}


def median_confidence(votes: list[dict[str, Any]]) -> tuple[float, list[float]]:
    mids = []
    for v in votes:
        low = v.get("p_low", v.get("confidence", 0.5) - 0.05)
        high = v.get("p_high", v.get("confidence", 0.5) + 0.05)
        mids.append((low + high) / 2)
    if not mids:
        return 0.5, [0.45, 0.55]
    mids.sort()
    mid = mids[len(mids) // 2]
    return mid, [min(mids), max(mids)]
