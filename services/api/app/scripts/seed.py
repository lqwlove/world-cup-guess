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
                if existing:
                    continue
                session.add(
                    Match(
                        id=row["id"],
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
                )

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
    match_id = "wc2026-final"
    result = await session.execute(
        select(Discussion).where(Discussion.match_id == match_id)
    )
    if result.scalars().first():
        return

    from uuid import uuid4

    discussion_id = uuid4()
    discussion = Discussion(
        id=discussion_id,
        match_id=match_id,
        status="completed",
        phase="Consensus",
        round=12,
        data_version="v1",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    session.add(discussion)

    demo_messages = [
        ("moderator", "STATEMENT", "Opening the tactical room for Argentina vs Spain.", [], []),
        ("data", "STATEMENT", "Argentina's last 5: 4W 1D, 11 GF / 3 GA per EV-home-form-001.", ["EV-home-form-001"], ["EV-home-form-001"]),
        ("squad", "STATEMENT", "Messi fit; Yamal fit for Spain.", ["EV-player-messi-001"], ["EV-player-messi-001", "EV-player-yamal-001"]),
        ("market", "STATEMENT", "Market implies home 48%, draw 26%, away 26%.", [], []),
        ("skeptic", "CHALLENGE", "@data Spain's xG trend in knockouts may be understated.", ["E-001"], []),
        ("data", "REBUTTAL", "E-001 acknowledged; EV-elo-001 still favors Argentina slightly.", ["E-001"], ["EV-elo-001"]),
        ("moderator", "CONSENSUS_FINAL", "Final consensus drafted for all plays.", [], []),
        ("skeptic", "ACK_WITH_RESERVATION", "Signed with reservation: counter-attack variance.", [], []),
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
            {"role": "skeptic", "summary": "Spain counter-attack efficiency may be underestimated."}
        ],
        "unresolved": [],
        "skeptic_ack": "ACK_WITH_RESERVATION",
    }
    session.add(
        ConsensusArtifact(
            match_id=match_id,
            discussion_id=discussion_id,
            schema_version="v1",
            json_data=artifact,
            strength="strong",
        )
    )

    # Default market snapshot for final
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

    await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
