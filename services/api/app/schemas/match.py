from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_serializer

from app.schemas.serializers import serialize_utc_datetime


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

    @field_serializer("kickoff_at")
    def _kickoff_utc(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class MatchDetailOut(MatchListOut):
    data_version: str
    latest_discussion_id: Optional[str] = None
    deliberation_error: Optional[str] = None


class MatchFactOut(BaseModel):
    fact_type: str
    payload: dict[str, Any]
    evidence_id: str
    source: str
    updated_at: datetime

    @field_serializer("updated_at")
    def _updated_utc(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


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

    @field_serializer("captured_at")
    def _captured_utc(self, value: datetime) -> str:
        return serialize_utc_datetime(value)


class MarketSnapshotImport(BaseModel):
    probabilities: dict[str, float]
    raw: Optional[dict[str, Any]] = None
    platform: str = "polymarket"
    source: str = "local_sync"


class MatchFilters(BaseModel):
    date: Optional[str] = None
    stage: Optional[str] = None
    group: Optional[str] = Field(default=None, alias="group_code")
