"""Extract votes and picks from debate messages."""

import re
from typing import Any

from app.deliberation.constants import SPECIALIST_ROLES

_PICK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("home", re.compile(r"主胜|主队胜|主赢|胜主|倾向主|看好主|押主|站主")),
    ("draw", re.compile(r"平局|打平|平手|和局|倾向平|看好平|押平")),
    ("away", re.compile(r"客胜|客队胜|客赢|倾向客|看好客|押客|站客")),
]


def infer_pick_from_text(content: str) -> str | None:
    if not content:
        return None
    scores = {k: 0 for k in ("home", "draw", "away")}
    for key, pat in _PICK_PATTERNS:
        if pat.search(content):
            scores[key] += 1
    if max(scores.values()) == 0:
        low = content.lower()
        if "home" in low:
            scores["home"] += 1
        if "draw" in low:
            scores["draw"] += 1
        if "away" in low:
            scores["away"] += 1
    top = max(scores, key=scores.get)
    return top if scores[top] > 0 else None


def extract_votes_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    votes: list[dict[str, Any]] = []
    for role in SPECIALIST_ROLES:
        pick: str | None = None
        confidence = 0.55
        for m in reversed(messages):
            if m.get("role") != role:
                continue
            if m.get("msg_type") not in ("STATEMENT", "CHALLENGE", "REBUTTAL", "SUPPORT", "REVISE"):
                continue
            pick = infer_pick_from_text(m.get("content", ""))
            if pick:
                if m.get("msg_type") == "CHALLENGE":
                    confidence = 0.45
                elif m.get("msg_type") in ("REBUTTAL", "SUPPORT"):
                    confidence = 0.62
                else:
                    confidence = 0.58
                break
        if pick:
            votes.append(
                {
                    "role": role,
                    "pick": pick,
                    "confidence": confidence,
                    "p_low": max(0.05, confidence - 0.08),
                    "p_high": min(0.95, confidence + 0.08),
                }
            )
    return votes


def score_top3_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, float]]:
    found: list[str] = []
    score_pat = re.compile(r"\b(\d{1,2})[-:：](\d{1,2})\b")
    for m in reversed(messages):
        if m.get("role") != "scoreline":
            continue
        for a, b in score_pat.findall(m.get("content", "")):
            s = f"{a}-{b}"
            if s not in found:
                found.append(s)
        if len(found) >= 3:
            break
    if not found:
        return [
            {"score": "2-1", "confidence": 0.2},
            {"score": "1-1", "confidence": 0.18},
            {"score": "1-0", "confidence": 0.15},
        ]
    confidences = [0.22, 0.18, 0.14]
    return [
        {"score": s, "confidence": confidences[i] if i < len(confidences) else 0.1}
        for i, s in enumerate(found[:3])
    ]
