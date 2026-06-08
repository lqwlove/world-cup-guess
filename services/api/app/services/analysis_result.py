"""Derive a single clear prediction from consensus artifact JSON."""

from typing import Any, Optional

PICK_LABELS = {
    "home": "主胜",
    "draw": "平局",
    "away": "客胜",
}


def _top_score(artifact: dict[str, Any]) -> Optional[str]:
    scores = (artifact.get("plays") or {}).get("score_top3") or []
    if not scores:
        return None
    best = max(scores, key=lambda s: float(s.get("confidence") or 0))
    return str(best.get("score") or "")


def _probs_from_market_edge(artifact: dict[str, Any]) -> dict[str, int]:
    edges = artifact.get("market_edge") or []
    raw: dict[str, float] = {}
    for row in edges:
        outcome = row.get("outcome")
        if outcome in ("home", "draw", "away"):
            raw[outcome] = float(row.get("consensus_p") or 0)
    if not raw:
        return {}
    total = sum(raw.values()) or 1.0
    return {k: int(round(v / total * 100)) for k, v in raw.items()}


def _normalize_probs(probs: dict[str, float]) -> dict[str, int]:
    total = sum(probs.values()) or 1.0
    rounded = {k: int(round(v / total * 100)) for k, v in probs.items()}
    diff = 100 - sum(rounded.values())
    if diff and rounded:
        top = max(rounded, key=rounded.get)
        rounded[top] += diff
    return rounded


def extract_analysis_result(artifact: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not artifact:
        return None

    prediction = artifact.get("prediction")
    if isinstance(prediction, dict) and prediction.get("pick"):
        pick = prediction["pick"]
        probs = prediction.get("probs") or {}
        pct = probs.get(pick)
        if pct is None and probs:
            pct = probs.get(pick, max(probs.values()))
        return {
            "pick": pick,
            "label": PICK_LABELS.get(pick, pick),
            "pct": int(pct) if pct is not None else None,
            "score": prediction.get("score") or _top_score(artifact),
            "probs": probs,
        }

    probs = _probs_from_market_edge(artifact)
    if not probs:
        pick = (artifact.get("plays") or {}).get("1x2", {}).get("pick")
        if pick in PICK_LABELS:
            conf = float((artifact.get("plays") or {}).get("1x2", {}).get("confidence") or 0.5)
            base = max(0.1, 1.0 - conf)
            probs = _normalize_probs(
                {
                    "home": conf if pick == "home" else base / 2,
                    "draw": conf if pick == "draw" else base / 2,
                    "away": conf if pick == "away" else base / 2,
                }
            )
        else:
            return None

    pick = max(probs, key=probs.get)
    return {
        "pick": pick,
        "label": PICK_LABELS.get(pick, pick),
        "pct": probs[pick],
        "score": _top_score(artifact),
        "probs": probs,
    }
