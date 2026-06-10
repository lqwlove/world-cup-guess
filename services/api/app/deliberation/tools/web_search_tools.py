"""Agent tools wrapping web search."""

import json
from typing import Any

from app.deliberation.runtime import get_session
from app.services.web_search_service import search_and_persist

ROLE_SEARCH_QUERIES: dict[str, list[str]] = {
    "data": [
        "{comp} {home} {away} 交锋 战绩 xG 进球数据",
        "{comp} {home} 小组赛 近况 统计",
        "{home} vs {away} 世界杯 历史 大数据",
    ],
    "squad": [
        "{comp} {home} 伤病 首发 阵容 预测",
        "{comp} {away} 伤病 停赛 阵容",
        "{home} vs {away} 战术 阵型 核心球员",
    ],
    "market": [
        "{home} vs {away} Polymarket 赔率 概率 变化",
        "{comp} {home} {away} 博彩 盘口 隐含概率",
        "{home} vs {away} 世界杯 赔率 分析",
    ],
    "skeptic": [
        "{comp} {home} vs {away} 冷门 爆冷 世界杯小组赛",
        "{away} 逼平 强队 世界杯 历史",
        "{home} 小组赛 慢热 被低估",
    ],
    "handicap": [
        "{home} vs {away} 让球 亚盘 盘口 分析",
        "{comp} {home} 让球 走势",
    ],
    "scoreline": [
        "{home} vs {away} 比分 预测 进球数",
        "{comp} {home} {away} 大小球 2.5",
    ],
}


async def tool_web_search(match_id: str, query: str) -> str:
    session = get_session()
    data = await search_and_persist(session, match_id, query)
    return json.dumps(data, ensure_ascii=False)[:6000]


def _format_queries(role: str, ctx: dict[str, Any]) -> list[str]:
    home = ctx.get("home_team", "主队")
    away = ctx.get("away_team", "客队")
    comp = ctx.get("competition", "2026世界杯")
    kickoff = ctx.get("kickoff_cn") or ctx.get("kickoff_at", "")
    templates = ROLE_SEARCH_QUERIES.get(role, ROLE_SEARCH_QUERIES["data"])
    return [
        t.format(comp=comp, home=home, away=away, kickoff=kickoff) for t in templates
    ]


async def tool_search_teams_latest_status(match_id: str, match_context: dict[str, Any]) -> str:
    home = match_context.get("home_team", "主队")
    away = match_context.get("away_team", "客队")
    queries = [
        f"{match_context.get('competition', '2026世界杯')} {home} 最新阵容 伤病 赛前",
        f"{match_context.get('competition', '2026世界杯')} {away} 最新阵容 伤病 赛前",
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


async def tool_role_web_search(match_id: str, role: str, match_context: dict[str, Any]) -> str:
    """Role-tailored web search queries."""
    queries = _format_queries(role, match_context)
    session = get_session()
    batch: list[dict[str, Any]] = []
    evidence_ids: list[str] = []

    for q in queries[:3]:
        data = await search_and_persist(session, match_id, q)
        batch.append({"query": q, "ok": data.get("ok"), "count": data.get("count", 0)})
        if data.get("evidence_id"):
            evidence_ids.append(data["evidence_id"])

    return json.dumps(
        {
            "ok": bool(evidence_ids),
            "role": role,
            "searches": batch,
            "evidence_ids": evidence_ids,
            "hint": "摘要已写入 web_intel，引用 evidence_id。",
        },
        ensure_ascii=False,
    )
