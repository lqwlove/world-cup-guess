"""Polymarket Gamma API integration."""

from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import MarketMapping, MarketSnapshot
from app.schemas.match import MarketMappingOut, MarketSnapshotOut

settings = get_settings()


async def get_market_for_match(session: AsyncSession, match_id: str) -> Optional[MarketSnapshotOut]:
    mapping_result = await session.execute(
        select(MarketMapping).where(
            MarketMapping.match_id == match_id,
            MarketMapping.platform == "polymarket",
        )
    )
    mapping = mapping_result.scalar_one_or_none()
    if not mapping:
        return None

    snap_result = await session.execute(
        select(MarketSnapshot)
        .where(MarketSnapshot.match_id == match_id)
        .order_by(desc(MarketSnapshot.captured_at))
        .limit(1)
    )
    snapshot = snap_result.scalar_one_or_none()
    if not snapshot:
        return None

    return MarketSnapshotOut(
        match_id=match_id,
        platform=snapshot.platform,
        probabilities={k: float(v) for k, v in snapshot.probabilities.items()},
        captured_at=snapshot.captured_at,
        mapping=MarketMappingOut(
            platform=mapping.platform,
            event_slug=mapping.event_slug,
            outcome_map=mapping.outcome_map,
            review_status=mapping.review_status,
        ),
    )


async def fetch_polymarket_snapshot(
    session: AsyncSession, match_id: str
) -> Optional[MarketSnapshot]:
    mapping_result = await session.execute(
        select(MarketMapping).where(
            MarketMapping.match_id == match_id,
            MarketMapping.platform == "polymarket",
        )
    )
    mapping = mapping_result.scalar_one_or_none()
    if not mapping:
        return None

    probabilities = await _fetch_probabilities(mapping)
    if not probabilities:
        return None

    snapshot = MarketSnapshot(
        match_id=match_id,
        platform="polymarket",
        probabilities=probabilities,
        raw={"event_slug": mapping.event_slug},
        captured_at=datetime.utcnow(),
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def _fetch_probabilities(mapping: MarketMapping) -> Optional[dict[str, float]]:
    """Fetch from Gamma API or return mock when unavailable."""
    slug = mapping.event_slug
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.polymarket_gamma_url}/events",
                params={"slug": slug},
            )
            if resp.status_code == 200:
                data = resp.json()
                probs = _parse_gamma_response(data, mapping.outcome_map)
                if probs:
                    return probs
    except Exception:
        pass

    # Fallback mock probabilities for demo / offline
    return _mock_probabilities(mapping.match_id)


def _parse_gamma_response(data: Any, outcome_map: dict[str, str]) -> Optional[dict[str, float]]:
    if not data:
        return None
    events = data if isinstance(data, list) else data.get("data", data.get("events", []))
    if not events:
        return None
    event = events[0] if isinstance(events, list) else events
    markets = event.get("markets", [])
    if not markets:
        return None

    probs: dict[str, float] = {}
    for market in markets:
        outcomes = market.get("outcomes") or []
        prices = market.get("outcomePrices") or market.get("prices") or []
        for i, outcome in enumerate(outcomes):
            price = float(prices[i]) if i < len(prices) else 0.0
            for key, mapped in outcome_map.items():
                if str(outcome).lower() == str(mapped).lower() or str(outcome).lower() in str(mapped).lower():
                    probs[key] = price
    if probs:
        total = sum(probs.values()) or 1.0
        return {k: v / total for k, v in probs.items()}
    return None


def _mock_probabilities(match_id: str) -> dict[str, float]:
    mocks = {
        "fifa-400021543": {"home": 0.48, "draw": 0.26, "away": 0.26},
        "fifa-400021541": {"home": 0.42, "draw": 0.28, "away": 0.30},
        "fifa-400021496": {"home": 0.55, "draw": 0.25, "away": 0.20},
    }
    return mocks.get(match_id, {"home": 0.33, "draw": 0.34, "away": 0.33})


def compute_market_edge(
    consensus_probs: dict[str, float], market_probs: dict[str, float]
) -> list[dict[str, float]]:
    rows = []
    for outcome, cp in consensus_probs.items():
        mp = market_probs.get(outcome, 0.0)
        rows.append(
            {
                "outcome": outcome,
                "consensus_p": round(cp, 4),
                "market_p": round(mp, 4),
                "edge": round(cp - mp, 4),
            }
        )
    rows.sort(key=lambda r: abs(r["edge"]), reverse=True)
    return rows
