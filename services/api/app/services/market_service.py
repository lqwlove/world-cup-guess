"""Polymarket Gamma API integration."""

import json
from datetime import datetime
from typing import Any, Optional

import httpx
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import MarketMapping, MarketSnapshot
from app.schemas.match import MarketMappingOut, MarketSnapshotOut

settings = get_settings()

DRAW_TOKENS = ("draw", "tie", "平局", "x")


async def has_market_mapping(session: AsyncSession, match_id: str) -> bool:
    result = await session.execute(
        select(MarketMapping.id).where(
            MarketMapping.match_id == match_id,
            MarketMapping.platform == "polymarket",
        )
    )
    return result.scalar_one_or_none() is not None


async def ensure_market_snapshot(session: AsyncSession, match_id: str) -> bool:
    """Fetch Polymarket snapshot when mapping exists but no snapshot yet."""
    if not await has_market_mapping(session, match_id):
        return False
    snap_result = await session.execute(
        select(MarketSnapshot.id)
        .where(MarketSnapshot.match_id == match_id)
        .limit(1)
    )
    if snap_result.scalar_one_or_none() is not None:
        return True
    snap = await fetch_polymarket_snapshot(session, match_id)
    return snap is not None


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

    parsed = await _fetch_event_probabilities(mapping)
    if not parsed:
        return None

    probabilities, raw_meta = parsed
    snapshot = MarketSnapshot(
        match_id=match_id,
        platform="polymarket",
        probabilities=probabilities,
        raw=raw_meta,
        captured_at=datetime.utcnow(),
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


async def _fetch_event_probabilities(
    mapping: MarketMapping,
) -> Optional[tuple[dict[str, float], dict[str, Any]]]:
    slug = mapping.event_slug
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.polymarket_gamma_url}/events",
                params={"slug": slug},
            )
            if resp.status_code == 200:
                data = resp.json()
                parsed = _parse_gamma_response(data, mapping.outcome_map)
                if parsed:
                    probs, markets_meta = parsed
                    return probs, {
                        "event_slug": slug,
                        "title": markets_meta.get("title"),
                        "volume": markets_meta.get("volume"),
                        "volume24hr": markets_meta.get("volume24hr"),
                        "markets": markets_meta.get("markets"),
                    }
    except Exception:
        pass

    mock = _mock_probabilities(mapping.match_id)
    if mock:
        return mock, {"event_slug": slug, "source": "mock"}
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            return [value]
    return [value]


def _yes_price(market: dict[str, Any]) -> Optional[float]:
    outcomes = _as_list(market.get("outcomes"))
    prices = _as_list(market.get("outcomePrices") or market.get("prices"))
    if not prices:
        return None
    for i, outcome in enumerate(outcomes):
        if str(outcome).lower() == "yes" and i < len(prices):
            return float(prices[i])
    return float(prices[0])


def _market_blob(market: dict[str, Any]) -> str:
    parts = [
        market.get("groupItemTitle"),
        market.get("question"),
        market.get("slug"),
        market.get("description"),
    ]
    return " ".join(str(p) for p in parts if p).lower()


def _outcome_key(blob: str, mapped: str, key: str) -> bool:
    token = str(mapped).lower().strip()
    if not token:
        return False
    if token in blob:
        return True
    if key == "draw":
        return any(t in blob for t in DRAW_TOKENS)
    return False


def _parse_gamma_response(
    data: Any, outcome_map: dict[str, str]
) -> Optional[tuple[dict[str, float], dict[str, Any]]]:
    if not data:
        return None
    events = data if isinstance(data, list) else data.get("data", data.get("events", []))
    if not events:
        return None
    event = events[0] if isinstance(events, list) else events
    markets = event.get("markets", [])
    if not markets:
        return None

    probs = _parse_split_yes_no_markets(markets, outcome_map)
    if not probs:
        probs = _parse_single_market_outcomes(markets, outcome_map)
    if not probs:
        return None

    total = sum(probs.values()) or 1.0
    normalized = {k: round(v / total, 4) for k, v in probs.items()}

    markets_meta = []
    for market in markets:
        yes_p = _yes_price(market)
        markets_meta.append(
            {
                "slug": market.get("slug"),
                "question": market.get("question"),
                "groupItemTitle": market.get("groupItemTitle"),
                "yes_price": yes_p,
                "volume": market.get("volume"),
            }
        )

    return normalized, {
        "title": event.get("title"),
        "volume": event.get("volume"),
        "volume24hr": event.get("volume24hr"),
        "markets": markets_meta,
    }


def _parse_split_yes_no_markets(
    markets: list[dict[str, Any]], outcome_map: dict[str, str]
) -> dict[str, float]:
    """FIFA WC style: one Yes/No market per outcome (home / draw / away)."""
    probs: dict[str, float] = {}
    for market in markets:
        yes_p = _yes_price(market)
        if yes_p is None:
            continue
        blob = _market_blob(market)
        for key in ("home", "draw", "away"):
            if key in probs:
                continue
            mapped = outcome_map.get(key, "")
            if _outcome_key(blob, mapped, key):
                probs[key] = yes_p
    return probs


def _parse_single_market_outcomes(
    markets: list[dict[str, Any]], outcome_map: dict[str, str]
) -> dict[str, float]:
    """Legacy: one market with named outcomes (home / draw / away)."""
    probs: dict[str, float] = {}
    for market in markets:
        outcomes = _as_list(market.get("outcomes"))
        prices = _as_list(market.get("outcomePrices") or market.get("prices"))
        for i, outcome in enumerate(outcomes):
            price = float(prices[i]) if i < len(prices) else 0.0
            outcome_l = str(outcome).lower()
            for key, mapped in outcome_map.items():
                mapped_l = str(mapped).lower()
                if outcome_l == mapped_l or mapped_l in outcome_l or outcome_l in mapped_l:
                    probs[key] = price
    return probs


def _mock_probabilities(match_id: str) -> Optional[dict[str, float]]:
    mocks = {
        "fifa-400021543": {"home": 0.48, "draw": 0.26, "away": 0.26},
        "fifa-400021541": {"home": 0.42, "draw": 0.28, "away": 0.30},
        "fifa-400021496": {"home": 0.55, "draw": 0.25, "away": 0.20},
    }
    return mocks.get(match_id)


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
