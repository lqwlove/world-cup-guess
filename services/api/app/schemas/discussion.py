from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DiscussionCreate(BaseModel):
    force_refresh: bool = False


class DiscussionOut(BaseModel):
    id: UUID
    match_id: str
    status: str
    mode: str = "analysis"
    phase: str
    round: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error_reason: Optional[str] = None


class ResumeDiscussion(BaseModel):
    reply: str


class FollowupChat(BaseModel):
    question: str


class MessageOut(BaseModel):
    seq: int
    role: str
    msg_type: str
    content: str
    refs: list[str] = []
    evidence_ids: list[str] = []
    phase: str
    created_at: datetime


class FeedbackCreate(BaseModel):
    match_id: str
    session_id: str
    vote: str  # up | down
