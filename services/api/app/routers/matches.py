from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.entities import Match, MatchFact
from app.schemas.match import FactsBundleOut, MatchDetailOut, MatchFactOut, MatchListOut
from app.services import match_service
from app.services.consensus_service import get_latest_consensus
from app.config import get_settings
from app.services.football_data_service import sync_match_facts
from app.services.market_service import get_market_for_match

settings = get_settings()

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.get("", response_model=list[MatchListOut])
async def list_matches(
    date: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    group: Optional[str] = Query(None, alias="group"),
    session: AsyncSession = Depends(get_session),
):
    return await match_service.list_matches(
        session, date_filter=date, stage=stage, group_code=group
    )


@router.get("/{match_id}", response_model=MatchDetailOut)
async def get_match(match_id: str, session: AsyncSession = Depends(get_session)):
    match = await match_service.get_match(session, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    return match


@router.get("/{match_id}/facts", response_model=FactsBundleOut)
async def get_facts(match_id: str, session: AsyncSession = Depends(get_session)):
    m = await session.get(Match, match_id)
    if not m:
        raise HTTPException(404, "Match not found")
    result = await session.execute(select(MatchFact).where(MatchFact.match_id == match_id))
    facts = [
        MatchFactOut(
            fact_type=f.fact_type,
            payload=f.payload,
            evidence_id=f.evidence_id,
            source=f.source,
            updated_at=f.updated_at,
        )
        for f in result.scalars().all()
    ]
    return FactsBundleOut(match_id=match_id, data_version=m.data_version, facts=facts)


@router.get("/{match_id}/market")
async def get_market(match_id: str, session: AsyncSession = Depends(get_session)):
    market = await get_market_for_match(session, match_id)
    if not market:
        return {"available": False, "message": "No market mapping"}
    return {"available": True, **market.model_dump()}


@router.post("/{match_id}/facts/sync")
async def sync_facts_from_football_data(
    match_id: str, session: AsyncSession = Depends(get_session)
):
    """Refresh structured facts for one match from football-data.org."""
    m = await session.get(Match, match_id)
    if not m:
        raise HTTPException(404, "Match not found")
    if not settings.football_data_api_key:
        raise HTTPException(
            503,
            "FOOTBALL_DATA_API_KEY is not configured",
        )
    try:
        count = await sync_match_facts(session, match_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"football-data.org error: {exc}") from exc

    return {"match_id": match_id, "facts_synced": count, "source": "football-data.org"}


@router.get("/{match_id}/consensus")
async def get_consensus(match_id: str, session: AsyncSession = Depends(get_session)):
    consensus = await get_latest_consensus(session, match_id)
    if not consensus:
        raise HTTPException(404, "No consensus yet")
    return consensus
