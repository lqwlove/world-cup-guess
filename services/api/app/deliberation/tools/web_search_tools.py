"""Agent tools wrapping web search."""

import json
from typing import Any

from app.deliberation.runtime import get_session
from app.services.web_search_service import search_and_persist


async def tool_web_search(match_id: str, query: str) -> str:
    session = get_session()
    data = await search_and_persist(session, match_id, query)
    return json.dumps(data, ensure_ascii=False)[:6000]


async def tool_search_teams_latest_status(match_id: str, match_context: dict[str, Any]) -> str:
    home = match_context.get("home_team", "主队")
    away = match_context.get("away_team", "客队")
    comp = match_context.get("competition", "2026世界杯")
    kickoff = match_context.get("kickoff_cn") or match_context.get("kickoff_at", "")

    queries = [
        f"{comp} {home} 最新阵容 伤病 赛前 {kickoff}",
        f"{comp} {away} 最新阵容 伤病 赛前",
        f"{home} vs {away} 世界杯 前瞻 分析",
    ]

    session = get_session()
    batch: list[dict[str, Any]] = []
    evidence_ids: list[str] = []

    for q in queries:
        data = await search_and_persist(session, match_id, q)
        batch.append({"query": q, "ok": data.get("ok"), "count": data.get("count", 0)})
        if data.get("evidence_id"):
            evidence_ids.append(data["evidence_id"])

    return json.dumps(
        {
            "ok": bool(evidence_ids),
            "teams": {"home": home, "away": away},
            "searches": batch,
            "evidence_ids": evidence_ids,
            "hint": "详细摘要已写入 match_facts（fact_type=web_intel），可用 list_match_facts 查看。",
        },
        ensure_ascii=False,
    )
