from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


class Match(SQLModel, table=True):
    __tablename__ = "matches"

    id: str = Field(primary_key=True, max_length=64)
    home_team: str = Field(max_length=128)
    away_team: str = Field(max_length=128)
    home_flag: Optional[str] = Field(default=None, max_length=8)
    away_flag: Optional[str] = Field(default=None, max_length=8)
    kickoff_at: datetime
    stage: str = Field(max_length=64)
    group_code: Optional[str] = Field(default=None, max_length=8)
    status: str = Field(default="scheduled", max_length=32)
    is_hot: bool = Field(default=False)
    data_version: str = Field(default="v1", max_length=32)


class MatchFact(SQLModel, table=True):
    __tablename__ = "match_facts"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: str = Field(foreign_key="matches.id", index=True, max_length=64)
    fact_type: str = Field(max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    evidence_id: str = Field(max_length=64, index=True)
    source: str = Field(max_length=256)
    data_version: str = Field(default="v1", max_length=32)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MarketMapping(SQLModel, table=True):
    __tablename__ = "market_mappings"
    __table_args__ = (UniqueConstraint("match_id", "platform", name="uq_match_platform"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: str = Field(foreign_key="matches.id", index=True, max_length=64)
    platform: str = Field(max_length=32)
    event_slug: str = Field(max_length=256)
    outcome_map: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    review_status: str = Field(default="approved", max_length=32)


class MarketSnapshot(SQLModel, table=True):
    __tablename__ = "market_snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: str = Field(foreign_key="matches.id", index=True, max_length=64)
    platform: str = Field(max_length=32)
    probabilities: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    raw: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    captured_at: datetime = Field(default_factory=datetime.utcnow)


class Discussion(SQLModel, table=True):
    __tablename__ = "discussions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    match_id: str = Field(foreign_key="matches.id", index=True, max_length=64)
    status: str = Field(default="pending", max_length=32)
    phase: str = Field(default="Opening", max_length=32)
    round: int = Field(default=0)
    data_version: str = Field(default="v1", max_length=32)
    cache_key: Optional[str] = Field(default=None, max_length=128)
    error_reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class DiscussionMessage(SQLModel, table=True):
    __tablename__ = "discussion_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    discussion_id: UUID = Field(foreign_key="discussions.id", index=True)
    seq: int
    role: str = Field(max_length=32)
    msg_type: str = Field(max_length=32)
    content: str = Field(sa_column=Column(Text))
    refs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    evidence_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    phase: str = Field(default="", max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ConsensusArtifact(SQLModel, table=True):
    __tablename__ = "consensus_artifacts"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: str = Field(foreign_key="matches.id", index=True, max_length=64)
    discussion_id: UUID = Field(foreign_key="discussions.id", index=True)
    schema_version: str = Field(default="v1", max_length=16)
    json_data: dict[str, Any] = Field(sa_column=Column("json", JSON))
    strength: str = Field(max_length=32)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Feedback(SQLModel, table=True):
    __tablename__ = "feedback"

    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: str = Field(index=True, max_length=64)
    session_id: str = Field(max_length=64)
    vote: str = Field(max_length=8)
    created_at: datetime = Field(default_factory=datetime.utcnow)
