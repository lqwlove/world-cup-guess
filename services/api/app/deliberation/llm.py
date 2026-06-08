"""LLM adapter with mock mode for development."""

import json
from typing import Any, Optional

from app.config import get_settings
from app.deliberation.constants import PHASE_LABELS, ROLE_LABELS

settings = get_settings()

# OpenAI 兼容 API 默认地址（可被 OPENAI_API_BASE 覆盖）
_OPENAI_COMPAT_BASES: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "volcengine": "https://ark.cn-beijing.volces.com/api/v3",
}

_DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "deepseek": "deepseek-chat",
    "volcengine": "doubao-pro-32k",
}


async def call_llm_json(prompt: str) -> dict:
    raw = await _call_llm(prompt)
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {"content": raw[:500]}


async def generate_role_message(
    *,
    role: str,
    phase: str,
    match_context: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    valid_evidence_ids: list[str],
) -> dict[str, Any]:
    if settings.mock_llm:
        return _mock_message(role, phase, match_context, valid_evidence_ids)

    prompt = _build_prompt(role, phase, match_context, recent_messages, valid_evidence_ids)
    raw = await _call_llm(prompt)
    try:
        data = json.loads(raw)
        return {
            "role": role,
            "msg_type": data.get("msg_type", "STATEMENT"),
            "content": data.get("content", ""),
            "refs": data.get("refs", []),
            "evidence_ids": data.get("evidence_ids", []),
        }
    except json.JSONDecodeError:
        return {
            "role": role,
            "msg_type": "STATEMENT",
            "content": raw[:500],
            "refs": [],
            "evidence_ids": [],
        }


def _format_market_snapshot(market: dict[str, float]) -> str:
    labels = {"home": "主胜", "draw": "平局", "away": "客胜"}
    parts = [f"{labels.get(k, k)}{v * 100:.0f}%" for k, v in market.items()]
    return " / ".join(parts) if parts else ""


def _mock_market_statement(match_context: dict[str, Any]) -> tuple[str, str, list[str]]:
    market = match_context.get("market_snapshot") or {}
    if market:
        summary = _format_market_snapshot(market)
        return (
            "STATEMENT",
            f"预测市场隐含：{summary}；需对照合议概率评估 Edge。",
            [],
        )
    return ("STATEMENT", "暂无预测市场映射，合议仅依据基本面与技术面。", [])


def _mock_message(
    role: str,
    phase: str,
    match_context: dict[str, Any],
    valid_evidence_ids: list[str],
) -> dict[str, Any]:
    home = match_context.get("home_team", "Home")
    away = match_context.get("away_team", "Away")
    ev = valid_evidence_ids[0] if valid_evidence_ids else "EV-demo-001"

    templates = {
        "data": ("STATEMENT", f"{home} 近期状态略占优，依据 {ev}。", [ev]),
        "squad": ("STATEMENT", f"{home} 对 {away} 关键球员阵容完整。", [ev] if valid_evidence_ids else []),
        "market": _mock_market_statement(match_context),
        "skeptic": ("CHALLENGE", f"@data {away} 反击效率可能被低估。", ["E-001"]),
        "handicap": ("STATEMENT", "主让 0.5 球盘口与近况基本匹配。", []),
        "scoreline": ("STATEMENT", "比分集中在 2-1、1-1、1-0。", []),
        "moderator": ("STATEMENT", f"{PHASE_LABELS.get(phase, phase)}：继续推进合议。", []),
    }

    if phase == "FinalVote" and role != "moderator":
        return {
            "role": role,
            "msg_type": "VOTE",
            "content": json.dumps({"pick": "home", "p_low": 0.52, "p_high": 0.62}),
            "refs": [],
            "evidence_ids": [],
        }

    if phase == "Consensus" and role == "moderator":
        return {
            "role": role,
            "msg_type": "CONSENSUS_FINAL",
            "content": "共识结论草案已定稿。",
            "refs": [],
            "evidence_ids": [],
        }

    if phase == "Consensus" and role == "skeptic":
        return {
            "role": role,
            "msg_type": "ACK_WITH_RESERVATION",
            "content": "保留意见签署：赛果方差仍偏高。",
            "refs": [],
            "evidence_ids": [],
        }

    if phase == "CrossExam" and role == "skeptic":
        msg_type, content, evs = ("CHALLENGE", f"@data 质疑 {away} 进攻转化数据。", [])
        return {"role": role, "msg_type": msg_type, "content": content, "refs": ["E-001"], "evidence_ids": evs}

    if phase == "CrossExam" and role == "data":
        return {
            "role": role,
            "msg_type": "REBUTTAL",
            "content": f"已回应 E-001，补充依据 {ev}。",
            "refs": ["E-001"],
            "evidence_ids": [ev],
        }

    msg_type, content, evs = templates.get(role, ("STATEMENT", "收到。", []))
    return {"role": role, "msg_type": msg_type, "content": content, "refs": [], "evidence_ids": evs}


def _build_prompt(
    role: str,
    phase: str,
    match_context: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    valid_evidence_ids: list[str],
) -> str:
    label = ROLE_LABELS.get(role, role)
    phase_zh = PHASE_LABELS.get(phase, phase)
    home = match_context.get("home_team", "")
    away = match_context.get("away_team", "")
    market = match_context.get("market_snapshot") or {}
    market_block = ""
    if market:
        market_block = f"\n预测市场隐含概率（Polymarket 快照）：{_format_market_snapshot(market)}"
    else:
        market_block = "\n预测市场：本场暂无映射数据，请勿编造市场概率。"
    market_role_hint = ""
    if role == "market":
        market_role_hint = "\n你是【市场官】：必须结合上述市场隐含概率，指出与其它角色共识的偏差或一致之处。"
    return f"""你是世界杯 AI 战术室中的【{label}】（角色代码 {role}）。
当前阶段：{phase_zh}（{phase}）
对阵：{home} vs {away}
可用证据编号：{valid_evidence_ids}{market_block}
最近讨论（JSON）：{json.dumps(recent_messages[-8:], ensure_ascii=False)}{market_role_hint}

请用简体中文撰写分析，语气专业、简洁，像战术室群聊发言。
仅输出 JSON，不要 markdown：{{"msg_type":"STATEMENT|CHALLENGE|REBUTTAL|SUPPORT|VOTE|ACK|ACK_WITH_RESERVATION|CONSENSUS_FINAL","content":"中文正文","refs":[],"evidence_ids":[]}}
规则：
- STATEMENT 陈述事实时必须填写 evidence_ids（来自可用证据列表）
- CHALLENGE / REBUTTAL / SUPPORT 须在 refs 中引用论点编号（如 E-001）
- VOTE 时 content 为 JSON 字符串：{{"pick":"home|draw|away","p_low":0.5,"p_high":0.6}}
- 禁止英文段落（专有名词如 EV-001 除外）
"""


def _openai_compat_base_url() -> Optional[str]:
    if settings.openai_api_base:
        return settings.openai_api_base.rstrip("/")
    return _OPENAI_COMPAT_BASES.get(settings.llm_provider)


def _resolve_model() -> str:
    if settings.llm_model:
        return settings.llm_model
    return _DEFAULT_MODELS.get(settings.llm_provider, "gpt-4o")


async def _call_llm(prompt: str) -> str:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from langchain_anthropic import ChatAnthropic
        from langchain_core.messages import HumanMessage

        llm = ChatAnthropic(model=settings.llm_model, api_key=settings.anthropic_api_key)
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        return resp.content

    base_url = _openai_compat_base_url()
    if settings.openai_api_key and base_url:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage

        llm = ChatOpenAI(
            model=_resolve_model(),
            api_key=settings.openai_api_key,
            base_url=base_url,
        )
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        return resp.content if isinstance(resp.content, str) else str(resp.content)

    return json.dumps(
        {"msg_type": "STATEMENT", "content": "模型服务暂不可用。", "refs": [], "evidence_ids": []},
        ensure_ascii=False,
    )
