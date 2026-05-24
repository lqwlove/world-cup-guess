"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("home_team", sa.String(128), nullable=False),
        sa.Column("away_team", sa.String(128), nullable=False),
        sa.Column("home_flag", sa.String(8)),
        sa.Column("away_flag", sa.String(8)),
        sa.Column("kickoff_at", sa.DateTime(), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("group_code", sa.String(8)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("is_hot", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("data_version", sa.String(32), nullable=False),
    )
    op.create_index("ix_matches_kickoff", "matches", ["kickoff_at"])

    op.create_table(
        "match_facts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("fact_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("data_version", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_match_facts_match_id", "match_facts", ["match_id"])

    op.create_table(
        "market_mappings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("event_slug", sa.String(256), nullable=False),
        sa.Column("outcome_map", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(32), nullable=False),
        sa.UniqueConstraint("match_id", "platform", name="uq_match_platform"),
    )

    op.create_table(
        "market_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("probabilities", sa.JSON(), nullable=False),
        sa.Column("raw", sa.JSON()),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_market_snapshots_match_id", "market_snapshots", ["match_id"])

    op.create_table(
        "discussions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("match_id", sa.String(64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("data_version", sa.String(32), nullable=False),
        sa.Column("cache_key", sa.String(128)),
        sa.Column("error_reason", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
    )
    op.create_index("ix_discussions_match_id", "discussions", ["match_id"])

    op.create_table(
        "discussion_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("discussion_id", sa.Uuid(), sa.ForeignKey("discussions.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("msg_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("refs", sa.JSON(), nullable=False),
        sa.Column("evidence_ids", sa.JSON(), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_discussion_messages_discussion_id", "discussion_messages", ["discussion_id"])

    op.create_table(
        "consensus_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(64), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("discussion_id", sa.Uuid(), sa.ForeignKey("discussions.id"), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("json", sa.JSON(), nullable=False),
        sa.Column("strength", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("match_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("vote", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("feedback")
    op.drop_table("consensus_artifacts")
    op.drop_table("discussion_messages")
    op.drop_table("discussions")
    op.drop_table("market_snapshots")
    op.drop_table("market_mappings")
    op.drop_table("match_facts")
    op.drop_table("matches")
