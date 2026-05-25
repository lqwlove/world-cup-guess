"""Load seed data from /seeds into PostgreSQL."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlmodel import SQLModel

from app.db import async_session_factory, engine
from app.models.entities import (
    ConsensusArtifact,
    Discussion,
    DiscussionMessage,
    Match,
    MatchFact,
    MarketMapping,
    MarketSnapshot,
)

SEEDS_DIR = Path("/seeds")
if not SEEDS_DIR.exists():
    SEEDS_DIR = Path(__file__).resolve().parents[4] / "seeds"


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with async_session_factory() as session:
        matches_path = SEEDS_DIR / "matches.json"
        if matches_path.exists():
            for row in json.loads(matches_path.read_text()):
                existing = await session.get(Match, row["id"])
                fields = dict(
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    home_flag=row.get("home_flag"),
                    away_flag=row.get("away_flag"),
                    kickoff_at=_parse_dt(row["kickoff_at"]),
                    stage=row["stage"],
                    group_code=row.get("group_code"),
                    status=row.get("status", "scheduled"),
                    is_hot=row.get("is_hot", False),
                    data_version=row.get("data_version", "v1"),
                )
                if existing:
                    for key, value in fields.items():
                        setattr(existing, key, value)
                else:
                    session.add(Match(id=row["id"], **fields))

        facts_path = SEEDS_DIR / "match_facts.sample.json"
        if facts_path.exists():
            for row in json.loads(facts_path.read_text()):
                result = await session.execute(
                    select(MatchFact).where(MatchFact.evidence_id == row["evidence_id"])
                )
                if result.scalar_one_or_none():
                    continue
                session.add(
                    MatchFact(
                        match_id=row["match_id"],
                        fact_type=row["fact_type"],
                        payload=row["payload"],
                        evidence_id=row["evidence_id"],
                        source=row["source"],
                        data_version="v1",
                    )
                )

        mappings_path = SEEDS_DIR / "market_mappings.json"
        if mappings_path.exists():
            for row in json.loads(mappings_path.read_text()):
                result = await session.execute(
                    select(MarketMapping).where(
                        MarketMapping.match_id == row["match_id"],
                        MarketMapping.platform == row["platform"],
                    )
                )
                if result.scalar_one_or_none():
                    continue
                session.add(
                    MarketMapping(
                        match_id=row["match_id"],
                        platform=row["platform"],
                        event_slug=row["event_slug"],
                        outcome_map=row["outcome_map"],
                        review_status=row.get("review_status", "approved"),
                    )
                )

        await session.commit()

        # Seed demo consensus for final match (P0 demo)
        await _seed_demo_discussion(session)


async def _seed_demo_discussion(session) -> None:
    match_id = "fifa-400021496"
    if not await session.get(Match, match_id):
        return

    result = await session.execute(
        select(Discussion).where(Discussion.match_id == match_id)
    )
    if result.scalars().first():
        return

    discussion = Discussion(
        match_id=match_id,
        status="completed",
        phase="Consensus",
        round=12,
        data_version="v1",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    session.add(discussion)
    await session.flush()

    discussion_id = discussion.id

    demo_messages = [
        ("moderator", "STATEMENT", "开启阿根廷 vs 阿尔及利亚战术室合议。", [], []),
        ("data", "STATEMENT", "阿根廷近5场 4胜1平，进11失3（EV-home-form-001）。", ["EV-home-form-001"], ["EV-home-form-001"]),
        ("squad", "STATEMENT", "梅西可出战；阿尔及利亚锋线完整。", ["EV-player-messi-001"], ["EV-player-messi-001"]),
        ("market", "STATEMENT", "市场隐含：主胜约 55%，平局 25%，客胜 20%。", [], []),
        ("skeptic", "CHALLENGE", "@data 阿尔及利亚防守反击效率可能被低估。", ["E-001"], []),
        ("data", "REBUTTAL", "已回应 E-001；EV-elo-001 仍略倾向主队。", ["E-001"], ["EV-elo-001"]),
        ("moderator", "CONSENSUS_FINAL", "三项玩法共识草案已形成。", [], []),
        ("skeptic", "ACK_WITH_RESERVATION", "保留意见签署：反击方差仍偏高。", [], []),
    ]
    for seq, (role, msg_type, content, refs, evidence_ids) in enumerate(demo_messages, start=1):
        session.add(
            DiscussionMessage(
                discussion_id=discussion_id,
                seq=seq,
                role=role,
                msg_type=msg_type,
                content=content,
                refs=refs,
                evidence_ids=evidence_ids,
                phase="Opening" if seq <= 4 else "CrossExam" if seq <= 6 else "Consensus",
            )
        )

    artifact = {
        "match_id": match_id,
        "status": "CONSENSUS_FINAL",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "consensus_strength": "strong",
        "plays": {
            "1x2": {
                "pick": "home",
                "confidence": 0.58,
                "confidence_band": [0.52, 0.64],
                "reasons": ["E-001", "EV-elo-001"],
                "dissent": None,
            },
            "score_top3": [
                {"score": "2-1", "confidence": 0.17},
                {"score": "1-1", "confidence": 0.14},
                {"score": "1-0", "confidence": 0.11},
            ],
            "handicap": {
                "line": "-0.5",
                "pick": "home",
                "confidence": 0.54,
                "abstain": False,
            },
        },
        "market_edge": [
            {"outcome": "home", "consensus_p": 0.58, "market_p": 0.48, "edge": 0.10},
            {"outcome": "draw", "consensus_p": 0.24, "market_p": 0.26, "edge": -0.02},
            {"outcome": "away", "consensus_p": 0.18, "market_p": 0.26, "edge": -0.08},
        ],
        "minority_opinions": [
            {"role": "skeptic", "summary": "阿尔及利亚反击效率可能被低估。"}
        ],
        "unresolved": [],
        "skeptic_ack": "ACK_WITH_RESERVATION",
    }
    result = await session.execute(
        select(MarketSnapshot).where(MarketSnapshot.match_id == match_id)
    )
    if not result.scalars().first():
        session.add(
            MarketSnapshot(
                match_id=match_id,
                platform="polymarket",
                probabilities={"home": 0.48, "draw": 0.26, "away": 0.26},
                raw={"mock": True},
            )
        )

    session.add(
        ConsensusArtifact(
            match_id=match_id,
            discussion_id=discussion_id,
            schema_version="v1",
            json_data=artifact,
            strength="strong",
        )
    )

    await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
