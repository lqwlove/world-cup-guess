from typing import Any, Optional, TypedDict


class DeliberationState(TypedDict, total=False):
    discussion_id: str
    match_id: str
    phase: str
    round: int
    max_rounds: int
    messages: list[dict[str, Any]]
    claims_registry: dict[str, str]
    facts_bundle: list[dict[str, Any]]
    market_snapshot: dict[str, float]
    match_context: dict[str, Any]
    valid_evidence_ids: list[str]
    challenge_streak: int
    last_challenge_round: int
    cross_exam_rounds: int
    votes_1x2: list[dict[str, Any]]
    vote_open: bool
    final_artifact: Optional[dict[str, Any]]
    skeptic_ack: Optional[str]
    unresolved: list[str]
    status: str
    error: Optional[str]
    opening_done: bool
    playbook_done: bool
