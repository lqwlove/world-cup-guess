"""Debate phase scheduling, unresolved tracking, and dynamic recall."""

from typing import Any, Optional

from app.deliberation.constants import ROLE_LABELS, SPECIALIST_ROLES

OPENING_ORDER = ["data", "squad", "market", "skeptic", "handicap", "scoreline"]
CROSS_EXAM_ORDER = ["skeptic", "market", "handicap", "scoreline", "data", "squad"]
BRAINSTORM_ORDER = ["data", "skeptic", "scoreline", "market"]
RECONCILE_ROLES = ["data", "squad", "market", "skeptic", "handicap", "scoreline"]

PHASE_OPENING = "Opening"
PHASE_CROSS = "CrossExam"
PHASE_BRAINSTORM = "Brainstorm"
PHASE_RECONCILE = "Reconcile"
PHASE_SUMMARY = "Summary"

CLAIM_TO_ROLE = {
    "data": "data",
    "squad": "squad",
    "market": "market",
    "skeptic": "skeptic",
    "handicap": "handicap",
    "scoreline": "scoreline",
}


def _is_speech(msg: dict[str, Any]) -> bool:
    return msg.get("msg_type") not in ("TOOL_CALL", "SYSTEM_QUESTION", "USER_REPLY")


def role_speech_count(messages: list[dict[str, Any]], role: str) -> int:
    return sum(1 for m in messages if m.get("role") == role and _is_speech(m))


def opening_complete(messages: list[dict[str, Any]]) -> bool:
    return all(role_speech_count(messages, r) >= 1 for r in OPENING_ORDER)


def cross_exam_complete(messages: list[dict[str, Any]]) -> bool:
    return all(role_speech_count(messages, r) >= 2 for r in OPENING_ORDER)


def brainstorm_complete(messages: list[dict[str, Any]]) -> bool:
    return all(role_speech_count(messages, r) >= 3 for r in BRAINSTORM_ORDER)


def detect_phase(messages: list[dict[str, Any]]) -> str:
    if not opening_complete(messages):
        return PHASE_OPENING
    if not cross_exam_complete(messages):
        return PHASE_CROSS
    if not brainstorm_complete(messages):
        return PHASE_BRAINSTORM
    return PHASE_RECONCILE


def update_unresolved(
    unresolved: list[str],
    msg: dict[str, Any],
) -> list[str]:
    refs = msg.get("refs") or []
    msg_type = msg.get("msg_type", "")
    current = list(unresolved)
    if msg_type == "CHALLENGE" and refs:
        for cid in refs:
            if cid not in current:
                current.append(cid)
    elif msg_type in ("REBUTTAL", "SUPPORT", "REVISE") and refs:
        current = [c for c in current if c not in refs]
    return current


def claim_responded(
    messages: list[dict[str, Any]],
    claim_id: str,
    after_index: int,
) -> bool:
    for m in messages[after_index + 1 :]:
        if not _is_speech(m):
            continue
        if m.get("msg_type") in ("REBUTTAL", "SUPPORT", "REVISE") and claim_id in (m.get("refs") or []):
            return True
    return False


def find_challenged_author(
    messages: list[dict[str, Any]],
    claim_authors: dict[str, str],
) -> Optional[str]:
    """If the latest challenge has no response yet, recall the claim author."""
    last_challenge_idx = -1
    last_challenge: dict[str, Any] | None = None
    for i, m in enumerate(messages):
        if m.get("msg_type") == "CHALLENGE" and m.get("refs"):
            last_challenge_idx = i
            last_challenge = m

    if not last_challenge or last_challenge_idx < 0:
        return None

    for cid in last_challenge.get("refs") or []:
        if claim_responded(messages, cid, last_challenge_idx):
            continue
        author = claim_authors.get(cid)
        if author in SPECIALIST_ROLES:
            challenger = last_challenge.get("role")
            if author != challenger:
                return author
    return None


def pick_reconcile_role(
    messages: list[dict[str, Any]],
    unresolved: list[str],
    claim_authors: dict[str, str],
) -> Optional[str]:
    if not unresolved:
        return None

    for cid in unresolved:
        author = claim_authors.get(cid)
        if author not in SPECIALIST_ROLES:
            continue
        responded = any(
            m.get("role") == author
            and m.get("msg_type") in ("REBUTTAL", "SUPPORT", "REVISE")
            and cid in (m.get("refs") or [])
            for m in messages
            if _is_speech(m)
        )
        if not responded:
            return author

    for role in RECONCILE_ROLES:
        if role_speech_count(messages, role) >= 5:
            continue
        return role
    return "skeptic" if unresolved else None


def pick_next_role(
    messages: list[dict[str, Any]],
    claim_authors: dict[str, str],
    unresolved: list[str],
) -> tuple[Optional[str], str, str]:
    """Return (next_role, phase, reason). next_role=None means finish."""
    phase = detect_phase(messages)

    recalled = find_challenged_author(messages, claim_authors)
    if recalled and opening_complete(messages):
        return (
            recalled,
            phase,
            f"动态召回：请{ROLE_LABELS.get(recalled, recalled)}回应最新质疑",
        )

    if phase == PHASE_OPENING:
        for role in OPENING_ORDER:
            if role_speech_count(messages, role) < 1:
                return role, phase, f"开场陈述，请{ROLE_LABELS.get(role, role)}发言"
        return None, phase, "开场完成"

    if phase == PHASE_CROSS:
        for role in CROSS_EXAM_ORDER:
            if role_speech_count(messages, role) < 2:
                return role, phase, f"交叉质询，请{ROLE_LABELS.get(role, role)}回应/质疑"
        return None, phase, "交叉质询完成"

    if phase == PHASE_BRAINSTORM:
        for role in BRAINSTORM_ORDER:
            if role_speech_count(messages, role) < 3:
                return (
                    role,
                    phase,
                    f"情景推演，请{ROLE_LABELS.get(role, role)}提出剧本/冷门",
                )
        return None, phase, "情景推演完成"

    if unresolved:
        role = pick_reconcile_role(messages, unresolved, claim_authors)
        if role:
            return (
                role,
                PHASE_RECONCILE,
                f"清账轮：仍有未回应论点 {', '.join(unresolved[:3])}",
            )
        return (
            "skeptic",
            PHASE_RECONCILE,
            f"清账轮（终审）：未决议题 {', '.join(unresolved[:3])}",
        )

    return None, PHASE_RECONCILE, "陈述、质询、推演已完成，进入总结"


def build_disagreement_matrix(
    messages: list[dict[str, Any]],
    claims_registry: dict[str, str],
    claim_authors: dict[str, str],
    unresolved: list[str],
) -> dict[str, Any]:
    challenges: list[dict[str, str]] = []
    for m in messages:
        if m.get("msg_type") != "CHALLENGE":
            continue
        for cid in m.get("refs") or []:
            challenges.append(
                {
                    "from": m.get("role", ""),
                    "claim_id": cid,
                    "author": claim_authors.get(cid, ""),
                    "snippet": (claims_registry.get(cid) or "")[:80],
                }
            )

    return {
        "claims": [
            {"id": cid, "author": claim_authors.get(cid, ""), "snippet": snip[:100]}
            for cid, snip in claims_registry.items()
        ],
        "challenges": challenges[-12:],
        "unresolved": unresolved,
    }
