"""Market tools for the market specialist."""

from typing import Any

from app.deliberation.runtime import get_session
from app.services.market_service import fetch_polymarket_snapshot


async def run_market_tools(match_id: str) -> dict[str, Any]:
    session = get_session()
    snap = await fetch_polymarket_snapshot(session, match_id)
    if not snap:
        return {"available": False, "probabilities": {}, "message": "本场暂无预测市场映射"}
    return {
        "available": True,
        "probabilities": snap.probabilities,
        "platform": snap.platform,
        "captured_at": snap.captured_at.isoformat() + "Z",
    }
