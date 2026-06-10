"""Market tools for the market specialist."""

from typing import Any

from app.deliberation.runtime import get_session
from app.services.market_service import fetch_polymarket_snapshot, get_extended_market_data


async def run_market_tools(match_id: str) -> dict[str, Any]:
    session = get_session()
    snap = await fetch_polymarket_snapshot(session, match_id)
    extended = await get_extended_market_data(session, match_id)

    if not snap and not extended.get("probabilities"):
        return {"available": False, "probabilities": {}, "message": "本场暂无预测市场映射"}

    probs = snap.probabilities if snap else extended.get("probabilities", {})
    return {
        "available": True,
        "probabilities": probs,
        "spread": extended.get("spread"),
        "totals": extended.get("totals"),
        "volume": extended.get("volume"),
        "volume24hr": extended.get("volume24hr"),
        "platform": "polymarket",
        "captured_at": snap.captured_at.isoformat() + "Z" if snap else None,
    }
