"""Web search for team news and pre-match intelligence."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.entities import MatchFact

logger = logging.getLogger(__name__)
settings = get_settings()

SOURCE = "web_search"


def _evidence_id(match_id: str, query: str) -> str:
    digest = hashlib.sha256(f"{match_id}:{query}".encode()).hexdigest()[:10]
    return f"EV-web-{digest}"


async def _tavily_search(query: str, max_results: int) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=25.0) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    items: list[dict[str, Any]] = []
    if data.get("answer"):
        items.append(
            {
                "title": "Tavily 摘要",
                "url": "",
                "snippet": str(data["answer"])[:800],
            }
        )
    for row in data.get("results") or []:
        items.append(
            {
                "title": row.get("title", ""),
                "url": row.get("url", ""),
                "snippet": (row.get("content") or row.get("snippet") or "")[:500],
            }
        )
    return items[:max_results]


def _duckduckgo_search_sync(query: str, max_results: int) -> list[dict[str, Any]]:
    try:
        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            rows = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": (r.get("body", r.get("snippet", "")) or "")[:500],
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []


async def search_web(query: str, *, max_results: int | None = None) -> dict[str, Any]:
    if not settings.web_search_enabled:
        return {"ok": False, "query": query, "error": "网络搜索未启用", "results": []}

    limit = max_results or settings.web_search_max_results
    q = query.strip()
    if not q:
        return {"ok": False, "query": query, "error": "搜索词为空", "results": []}

    try:
        if settings.tavily_api_key:
            results = await _tavily_search(q, limit)
            provider = "tavily"
        else:
            results = await asyncio.to_thread(_duckduckgo_search_sync, q, limit)
            provider = "duckduckgo"
        return {
            "ok": bool(results),
            "query": q,
            "provider": provider,
            "results": results,
            "count": len(results),
        }
    except Exception as exc:
        logger.exception("web search error for %r", q)
        return {"ok": False, "query": q, "error": str(exc), "results": []}


async def persist_web_intel(
    session: AsyncSession,
    match_id: str,
    query: str,
    search_payload: dict[str, Any],
) -> str:
    """Save search summary as match_fact for evidence_id citation."""
    evidence_id = _evidence_id(match_id, query)
    snippets = [
        f"{r.get('title', '')}: {r.get('snippet', '')[:200]}"
        for r in search_payload.get("results") or []
    ]
    payload = {
        "query": query,
        "provider": search_payload.get("provider"),
        "summary": " | ".join(snippets)[:2000] if snippets else "无结果",
        "sources": [r.get("url") for r in search_payload.get("results") or [] if r.get("url")][:5],
        "searched_at": datetime.utcnow().isoformat() + "Z",
    }

    result = await session.execute(
        select(MatchFact).where(MatchFact.evidence_id == evidence_id)
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.payload = payload
        existing.updated_at = datetime.utcnow()
    else:
        session.add(
            MatchFact(
                match_id=match_id,
                fact_type="web_intel",
                evidence_id=evidence_id,
                source=SOURCE,
                payload=payload,
                data_version="web",
            )
        )
    await session.commit()
    return evidence_id


async def search_and_persist(
    session: AsyncSession,
    match_id: str,
    query: str,
) -> dict[str, Any]:
    data = await search_web(query)
    if data.get("ok") and data.get("results"):
        ev = await persist_web_intel(session, match_id, query, data)
        data["evidence_id"] = ev
    return data
