"""Fact tools for specialist agents (read from match_facts)."""

from typing import Any

from sqlalchemy import select

from app.deliberation.runtime import get_session
from app.models.entities import MatchFact


async def list_facts(match_id: str) -> list[dict[str, Any]]:
    session = get_session()
    result = await session.execute(select(MatchFact).where(MatchFact.match_id == match_id))
    return [
        {
            "fact_type": f.fact_type,
            "payload": f.payload,
            "evidence_id": f.evidence_id,
            "source": f.source,
        }
        for f in result.scalars().all()
    ]


async def get_facts_by_types(match_id: str, fact_types: list[str]) -> list[dict[str, Any]]:
    facts = await list_facts(match_id)
    allowed = set(fact_types)
    return [f for f in facts if f["fact_type"] in allowed]


async def run_data_tools(match_id: str) -> dict[str, Any]:
    facts = await get_facts_by_types(match_id, ["recent_form", "head_to_head", "technical", "standing"])
    evidence_ids = [f["evidence_id"] for f in facts]
    return {"facts": facts, "evidence_ids": evidence_ids}


async def run_squad_tools(match_id: str) -> dict[str, Any]:
    facts = await get_facts_by_types(match_id, ["key_player", "squad_snapshot"])
    evidence_ids = [f["evidence_id"] for f in facts]
    return {"facts": facts, "evidence_ids": evidence_ids}
