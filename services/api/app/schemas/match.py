from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class MatchListOut(BaseModel):
    id: str
    home_team: str
    away_team: str
    home_flag: Optional[str] = None
    away_flag: Optional[str] = None
    kickoff_at: datetime
    stage: str
    group_code: Optional[str] = None
    status: str
    is_hot: bool = False
    deliberation_status: str = "none"  # none | generating | ready | partial | failed


class MatchDetailOut(MatchListOut):
    data_version: str


class MatchFactOut(BaseModel):
    fact_type: str
    payload: dict[str, Any]
    evidence_id: str
    source: str
    updated_at: datetime


class FactsBundleOut(BaseModel):
    match_id: str
    data_version: str
    facts: list[MatchFactOut]


class MarketMappingOut(BaseModel):
    platform: str
    event_slug: str
    outcome_map: dict[str, Any]
    review_status: str


class MarketSnapshotOut(BaseModel):
    match_id: str
    platform: str
    probabilities: dict[str, float]
    captured_at: datetime
    mapping: Optional[MarketMappingOut] = None


class MatchFilters(BaseModel):
    date: Optional[str] = None
    stage: Optional[str] = None
    group: Optional[str] = Field(default=None, alias="group_code")
