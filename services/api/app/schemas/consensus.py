from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Play1x2(BaseModel):
    pick: str
    confidence: float
    confidence_band: list[float] = Field(min_length=2, max_length=2)
    reasons: list[str] = []
    dissent: Optional[str] = None


class PlayScore(BaseModel):
    score: str
    confidence: float


class PlayHandicap(BaseModel):
    line: str
    pick: str
    confidence: float
    abstain: bool = False
    reasons: list[str] = []


class MarketEdgeRow(BaseModel):
    outcome: str
    consensus_p: float
    market_p: float
    edge: float


class MinorityOpinion(BaseModel):
    role: str
    summary: str


class ConsensusPlays(BaseModel):
    model_config = {"populate_by_name": True}

    one_x_two: Play1x2 = Field(alias="1x2")
    score_top3: list[PlayScore]
    handicap: PlayHandicap


class ConsensusArtifactSchema(BaseModel):
    match_id: str
    status: Literal["CONSENSUS_FINAL", "PARTIAL_CONSENSUS"]
    generated_at: datetime
    consensus_strength: Literal["strong", "weak", "partial"]
    plays: ConsensusPlays
    market_edge: list[MarketEdgeRow] = []
    minority_opinions: list[MinorityOpinion] = []
    unresolved: list[str] = []
    skeptic_ack: Literal["ACK", "ACK_WITH_RESERVATION", "PENDING"]


class ConsensusArtifactOut(BaseModel):
    match_id: str
    discussion_id: str
    schema_version: str
    strength: str
    artifact: dict[str, Any]
    created_at: datetime
