from typing import Any, Literal, Optional, TypedDict

SupervisorAction = Literal["call_agent", "ask_user", "finish", "partial"]


class WarRoomState(TypedDict, total=False):
    discussion_id: str
    match_id: str
    mode: Literal["analysis", "followup"]
    status: str
    phase: str
    turn: int
    max_turns: int
    messages: list[dict[str, Any]]
    claims_registry: dict[str, str]
    match_context: dict[str, Any]
    valid_evidence_ids: list[str]
    market_snapshot: dict[str, float]
    specialist_outputs: dict[str, Any]
    supervisor_action: SupervisorAction
    next_role: Optional[str]
    supervisor_reason: str
    pending_user_question: Optional[str]
    awaiting_user: bool
    user_reply: Optional[str]
    supervisor_trace: list[dict[str, Any]]
    votes_1x2: list[dict[str, Any]]
    final_artifact: Optional[dict[str, Any]]
    skeptic_ack: Optional[str]
    unresolved: list[str]
    error: Optional[str]
    persisted_count: int
    resume_to_supervisor: bool


# Legacy alias for old graph tests
DeliberationState = WarRoomState
