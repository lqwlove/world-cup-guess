"""LangChain tools for specialist agents (agent decides when to call)."""

import json
from typing import Any, Callable, Coroutine

from langchain_core.tools import StructuredTool

from app.config import get_settings
from app.deliberation.runtime import get_session
from app.deliberation.tools.facts import (
    facts_to_json,
    list_facts,
    run_data_tools,
    run_squad_tools,
)
from app.deliberation.tools.market import run_market_tools
from app.deliberation.tools.web_search_tools import (
    tool_role_web_search,
    tool_search_teams_latest_status,
    tool_web_search,
)
from app.services.football_data_service import sync_match_facts

settings = get_settings()


def _tool(
    *,
    name: str,
    description: str,
    coro: Callable[..., Coroutine[Any, Any, str]],
) -> StructuredTool:
    return StructuredTool.from_function(
        coroutine=coro,
        name=name,
        description=description,
    )


def _web_toolkit(match_id: str, role: str, ctx: dict[str, Any]) -> list[StructuredTool]:
    async def web_search(query: str) -> str:
        if not settings.web_search_enabled:
            return json.dumps({"ok": False, "error": "网络搜索未启用"}, ensure_ascii=False)
        return await tool_web_search(match_id, query)

    async def search_teams_latest_status() -> str:
        if not settings.web_search_enabled:
            return json.dumps({"ok": False, "error": "网络搜索未启用"}, ensure_ascii=False)
        return await tool_search_teams_latest_status(match_id, ctx)

    async def search_for_role() -> str:
        if not settings.web_search_enabled:
            return json.dumps({"ok": False, "error": "网络搜索未启用"}, ensure_ascii=False)
        return await tool_role_web_search(match_id, role, ctx)

    return [
        _tool(
            name="web_search",
            description="按关键词搜索最新足球资讯（伤病、停赛、阵容、赔率、冷门等）。",
            coro=web_search,
        ),
        _tool(
            name="search_teams_latest_status",
            description="搜索主客队最新赛前情报（阵容、伤病），写入 web_intel。",
            coro=search_teams_latest_status,
        ),
        _tool(
            name="search_for_role",
            description=f"按【{role}】职责定制搜索 query，获取更垂直的最新情报。",
            coro=search_for_role,
        ),
    ]


def build_tools_for_role(
    role: str,
    match_id: str,
    specialist_outputs: dict[str, Any] | None = None,
    match_context: dict[str, Any] | None = None,
) -> list[StructuredTool]:
    outputs = specialist_outputs or {}
    ctx = match_context or {}

    async def sync_facts_from_football_data() -> str:
        if not settings.football_data_api_key:
            return json.dumps(
                {"ok": False, "error": "未配置 FOOTBALL_DATA_API_KEY"},
                ensure_ascii=False,
            )
        session = get_session()
        try:
            count = await sync_match_facts(session, match_id)
            await session.commit()
            facts = await list_facts(match_id)
            return json.dumps(
                {
                    "ok": True,
                    "synced": count,
                    "evidence_ids": [f["evidence_id"] for f in facts],
                    "fact_types": list({f["fact_type"] for f in facts}),
                },
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)

    async def get_data_facts() -> str:
        data = await run_data_tools(match_id)
        return facts_to_json(data.get("facts") or [])

    async def get_squad_facts() -> str:
        data = await run_squad_tools(match_id)
        return facts_to_json(data.get("facts") or [])

    async def list_match_facts() -> str:
        facts = await list_facts(match_id)
        return facts_to_json(facts)

    async def get_polymarket_snapshot() -> str:
        data = await run_market_tools(match_id)
        return json.dumps(data, ensure_ascii=False)

    async def get_peer_summaries() -> str:
        lines = []
        for r, v in outputs.items():
            if not isinstance(v, dict):
                continue
            lines.append(
                {
                    "role": r,
                    "summary": v.get("full_content") or v.get("summary", ""),
                }
            )
        return json.dumps({"peers": lines}, ensure_ascii=False)

    common = [
        _tool(
            name="sync_facts_from_football_data",
            description="从 football-data.org 同步本场结构化数据。",
            coro=sync_facts_from_football_data,
        ),
        _tool(
            name="list_match_facts",
            description="列出本场所有已入库事实及 evidence_id。",
            coro=list_match_facts,
        ),
    ]

    web = _web_toolkit(match_id, role, ctx)

    if role == "data":
        return common + web + [
            _tool(
                name="get_data_facts",
                description="获取近况、交锋、技术统计、积分榜、网络情报。",
                coro=get_data_facts,
            ),
        ]

    if role == "squad":
        return common + web + [
            _tool(
                name="get_squad_facts",
                description="获取关键球员、阵容快照、网络情报。",
                coro=get_squad_facts,
            ),
        ]

    if role == "market":
        return web + [
            _tool(
                name="get_polymarket_snapshot",
                description="获取 Polymarket 胜平负、让球、大小球隐含概率。",
                coro=get_polymarket_snapshot,
            ),
            _tool(
                name="list_match_facts",
                description="列出本场已入库事实（辅助判断基本面）。",
                coro=list_match_facts,
            ),
        ]

    return web + [
        _tool(
            name="get_peer_summaries",
            description="获取其他专家在本场合议中的完整发言（非摘要）。",
            coro=get_peer_summaries,
        ),
        _tool(
            name="list_match_facts",
            description="列出本场结构化事实，用于核验他人观点。",
            coro=list_match_facts,
        ),
    ]
