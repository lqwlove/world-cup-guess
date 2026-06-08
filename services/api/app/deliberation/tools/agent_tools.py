"""LangChain tools for specialist agents (agent decides when to call)."""

import json
from typing import Any, Callable, Coroutine

from langchain_core.tools import StructuredTool

from app.config import get_settings
from app.deliberation.runtime import get_session
from app.deliberation.tools.facts import (
    facts_to_json,
    get_facts_by_types,
    list_facts,
    run_data_tools,
    run_squad_tools,
)
from app.deliberation.tools.market import run_market_tools
from app.deliberation.tools.web_search_tools import (
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


def build_tools_for_role(
    role: str,
    match_id: str,
    specialist_outputs: dict[str, Any] | None = None,
    match_context: dict[str, Any] | None = None,
) -> list[StructuredTool]:
    outputs = specialist_outputs or {}
    ctx = match_context or {}

    async def sync_facts_from_football_data() -> str:
        """从 football-data.org 拉取并写入本场结构化事实（主客队近况、交锋等）。"""
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
        """读取本场数据类事实：近况、交锋、技术统计、积分榜（来自数据库）。"""
        data = await run_data_tools(match_id)
        return facts_to_json(data.get("facts") or [])

    async def get_squad_facts() -> str:
        """读取本场阵容类事实：关键球员、阵容快照（来自数据库）。"""
        data = await run_squad_tools(match_id)
        return facts_to_json(data.get("facts") or [])

    async def list_match_facts() -> str:
        """列出本场全部已入库事实（含 evidence_id）。"""
        facts = await list_facts(match_id)
        return facts_to_json(facts)

    async def get_polymarket_snapshot() -> str:
        """获取预测市场 Polymarket 隐含概率快照。"""
        data = await run_market_tools(match_id)
        return json.dumps(data, ensure_ascii=False)

    async def get_peer_summaries() -> str:
        """读取其他专家在本场合议中的发言摘要。"""
        lines = []
        for r, v in outputs.items():
            if isinstance(v, dict) and v.get("summary"):
                lines.append({"role": r, "summary": v["summary"][:300]})
        return json.dumps({"peers": lines}, ensure_ascii=False)

    async def web_search(query: str) -> str:
        """在网上搜索与 query 相关的最新足球资讯（伤病、阵容、赛前动态等）。"""
        if not settings.web_search_enabled:
            return json.dumps({"ok": False, "error": "网络搜索未启用"}, ensure_ascii=False)
        return await tool_web_search(match_id, query)

    async def search_teams_latest_status() -> str:
        """搜索本场主客队最新状态、伤病与阵容消息，并写入 web_intel 事实。"""
        if not settings.web_search_enabled:
            return json.dumps({"ok": False, "error": "网络搜索未启用"}, ensure_ascii=False)
        return await tool_search_teams_latest_status(match_id, ctx)

    web_tools = [
        _tool(
            name="web_search",
            description=(
                "按关键词搜索最新足球资讯（伤病、停赛、阵容、教练言论等）。"
                "结果会写入 match_facts（web_intel），可引用返回的 evidence_id。"
            ),
            coro=web_search,
        ),
        _tool(
            name="search_teams_latest_status",
            description=(
                "一键搜索本场主客队最新赛前情报（阵容、伤病、状态）。"
                "建议在 sync/get_*_facts 之后调用，补充结构化数据之外的动态信息。"
            ),
            coro=search_teams_latest_status,
        ),
    ]

    common = [
        _tool(
            name="sync_facts_from_football_data",
            description=(
                "从 football-data.org 同步本场赛前数据到数据库。"
                "当 get_data_facts / get_squad_facts 返回空时，应先调用本工具再读取。"
            ),
            coro=sync_facts_from_football_data,
        ),
        _tool(
            name="list_match_facts",
            description="列出本场所有已入库事实及 evidence_id。",
            coro=list_match_facts,
        ),
    ]

    if role == "data":
        return common + web_tools + [
            _tool(
                name="get_data_facts",
                description="获取主客队近况、历史交锋、技术统计、积分榜、网络情报等数据类事实。",
                coro=get_data_facts,
            ),
        ]

    if role == "squad":
        return common + web_tools + [
            _tool(
                name="get_squad_facts",
                description="获取关键球员、阵容快照、网络情报等阵容类事实。",
                coro=get_squad_facts,
            ),
        ]

    if role == "market":
        return [
            _tool(
                name="get_polymarket_snapshot",
                description="获取 Polymarket 预测市场隐含概率（主胜/平/客胜）。",
                coro=get_polymarket_snapshot,
            ),
            _tool(
                name="list_match_facts",
                description="列出本场已入库事实（辅助判断基本面）。",
                coro=list_match_facts,
            ),
        ]

    # skeptic / handicap / scoreline
    return [
        _tool(
            name="get_peer_summaries",
            description="获取数据官、阵容官、市场官等已发言专家的摘要。",
            coro=get_peer_summaries,
        ),
        _tool(
            name="list_match_facts",
            description="列出本场结构化事实，用于核验他人观点。",
            coro=list_match_facts,
        ),
    ]
