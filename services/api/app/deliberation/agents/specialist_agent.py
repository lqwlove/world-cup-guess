"""Run a specialist with LangChain tool-calling (agent chooses which tools to invoke)."""

import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.config import get_settings
from app.deliberation.constants import ROLE_LABELS
from app.deliberation.llm import call_llm_json, get_tool_chat_model
from app.deliberation.match_brief import (
    fallback_statement,
    format_match_brief,
    is_neutral_content,
    is_vacuous_content,
)
from app.deliberation.role_prompts import (
    OPINION_RULES,
    ROLE_DEBATE_GUIDE,
    cross_exam_instruction,
    format_claims_for_prompt,
)
from app.deliberation.state import WarRoomState
from app.deliberation.activity import publish_tool_call
from app.deliberation.tools.agent_tools import build_tools_for_role
from app.deliberation.tools.facts import reload_evidence_ids, run_data_tools, run_squad_tools
from app.deliberation.tools.market import run_market_tools

settings = get_settings()
MAX_TOOL_ROUNDS = 5

_AGENT_RULES = """
【硬性规则】
1. 2026 世界杯正赛，比赛背景已给出，禁止索要赛事类型、时间、场地、名单。
2. 发言前必须先调用工具获取数据；数据为空时先 sync_facts_from_football_data 再 get_*_facts。
3. 需要最新伤病/阵容/赛前动态时，调用 search_teams_latest_status 或 web_search，引用 web_intel 的 evidence_id。
4. 引用结构化事实必须填 evidence_ids；质疑/支持前人观点必须填 refs（如 E-001）。
5. 禁止空话、「请提供」「待补充」。
"""


async def _mock_tool_run(role: str, match_id: str, outputs: dict[str, Any]) -> tuple[list[dict], dict[str, Any]]:
    """MOCK_LLM：模拟 agent 按需调工具。"""
    trace: list[dict[str, Any]] = []
    aggregated: dict[str, Any] = {"facts": [], "market": {}, "peers": outputs}

    if role in ("data", "squad"):
        trace.append({"tool": "sync_facts_from_football_data", "args": {}})
        trace.append({"tool": "search_teams_latest_status", "args": {}})
        trace.append({"tool": "get_data_facts" if role == "data" else "get_squad_facts", "args": {}})
        if role == "data":
            aggregated = await run_data_tools(match_id)
        else:
            aggregated = await run_squad_tools(match_id)
    elif role == "market":
        trace.append({"tool": "get_polymarket_snapshot", "args": {}})
        aggregated = await run_market_tools(match_id)
    else:
        trace.append({"tool": "get_peer_summaries", "args": {}})
        aggregated = {"peers": outputs}

    return trace, aggregated


async def _run_tool_loop(
    role: str,
    match_id: str,
    system_text: str,
    specialist_outputs: dict[str, Any],
    match_context: dict[str, Any],
    discussion_id: str = "",
) -> tuple[list[dict[str, Any]], list[Any]]:
    tools = build_tools_for_role(role, match_id, specialist_outputs, match_context)
    tool_map = {t.name: t for t in tools}
    llm = get_tool_chat_model().bind_tools(tools)

    messages: list[Any] = [
        SystemMessage(content=system_text),
        HumanMessage(
            content=(
                "请调用工具获取本场分析所需数据，获取足够后停止调工具。"
                "数据/阵容官：无事实时先 sync_facts_from_football_data，再 search_teams_latest_status 补充最新动态，"
                "最后 get_data_facts 或 get_squad_facts。"
            )
        ),
    ]
    trace: list[dict[str, Any]] = []
    tool_index = 0

    for _ in range(MAX_TOOL_ROUNDS):
        ai: AIMessage = await llm.ainvoke(messages)
        if not ai.tool_calls:
            messages.append(ai)
            break
        messages.append(ai)
        for tc in ai.tool_calls:
            name = tc["name"]
            args = tc.get("args") or {}
            tool = tool_map.get(name)
            if not tool:
                result = json.dumps({"error": f"unknown tool {name}"}, ensure_ascii=False)
            else:
                result = await tool.ainvoke(args)
            preview = str(result)[:300]
            tool_index += 1
            trace.append(
                {
                    "tool": name,
                    "args": args,
                    "result_preview": preview,
                }
            )
            if discussion_id:
                await publish_tool_call(
                    discussion_id,
                    role=role,
                    tool=name,
                    args=args,
                    result_preview=preview,
                    index=tool_index,
                )
            messages.append(
                ToolMessage(content=str(result), tool_call_id=tc["id"])
            )

    return trace, messages


async def _finalize_message(
    role: str,
    state: WarRoomState,
    tool_messages: list[Any],
    tool_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    ctx = dict(state.get("match_context", {}))
    match_id = state["match_id"]
    valid = await reload_evidence_ids(match_id) or state.get("valid_evidence_ids", [])

    # Collect tool result text from ToolMessages
    tool_results_text = "\n".join(
        m.content for m in tool_messages if isinstance(m, ToolMessage)
    )[:5000]

    aggregated: dict[str, Any] = {"facts": []}
    if role == "data":
        aggregated = await run_data_tools(match_id)
    elif role == "squad":
        aggregated = await run_squad_tools(match_id)
    elif role == "market":
        aggregated = await run_market_tools(match_id)

    label = ROLE_LABELS.get(role, role)
    messages = state.get("messages", [])
    registry = state.get("claims_registry", {})
    persona = ROLE_DEBATE_GUIDE.get(role, f"你是【{label}】，要有鲜明观点。")
    exam = cross_exam_instruction(role, messages)

    prompt = f"""{persona}
{format_match_brief(ctx)}

【你通过工具获取的数据】
{tool_results_text or json.dumps(aggregated, ensure_ascii=False)[:4000]}

【可用 evidence_id】{valid}

【场上已有论点】
{format_claims_for_prompt(registry)}

【最近讨论】
{json.dumps(messages[-8:], ensure_ascii=False)}

{exam}

{_AGENT_RULES}
{OPINION_RULES}

输出 JSON：
{{"msg_type":"STATEMENT|CHALLENGE|REBUTTAL|SUPPORT","content":"简体中文 100-260字，观点鲜明","refs":["E-001"],"evidence_ids":[]}}
说明：CHALLENGE/REBUTTAL/SUPPORT 时 refs 必填；STATEMENT 引用事实时 evidence_ids 必填。
"""
    data = await call_llm_json(prompt)
    content = data.get("content", "")
    msg = {
        "role": role,
        "msg_type": data.get("msg_type", "STATEMENT"),
        "content": content,
        "refs": data.get("refs", []),
        "evidence_ids": data.get("evidence_ids", []),
    }
    if is_vacuous_content(content) or is_neutral_content(content):
        text, evs, msg_type, refs = fallback_statement(
            role, ctx, aggregated, valid, messages, registry
        )
        msg["content"] = text
        msg["msg_type"] = msg_type
        msg["evidence_ids"] = evs
        msg["refs"] = refs

    msg["_tool_trace"] = tool_trace
    msg["_aggregated"] = aggregated
    return msg


async def run_specialist_agent(role: str, state: WarRoomState) -> dict[str, Any]:
    match_id = state["match_id"]
    ctx = dict(state.get("match_context", {}))
    outputs = state.get("specialist_outputs", {})
    label = ROLE_LABELS.get(role, role)
    persona = ROLE_DEBATE_GUIDE.get(role, "")
    system_text = (
        f"你是世界杯战术室【{label}】，战术辩论席成员，不是中立解说员。\n"
        f"{persona}\n{format_match_brief(ctx)}\n"
        f"你可以使用工具获取事实数据，不要向用户索要基础赛况。\n"
        f"{_AGENT_RULES}\n{OPINION_RULES}"
    )

    if settings.mock_llm:
        tool_trace, aggregated = await _mock_tool_run(role, match_id, outputs)
        valid = await reload_evidence_ids(match_id) or state.get("valid_evidence_ids", [])
        registry = state.get("claims_registry", {})
        text, evs, msg_type, refs = fallback_statement(
            role, ctx, aggregated, valid, state.get("messages", []), registry
        )
        return {
            "role": role,
            "msg_type": msg_type,
            "content": text,
            "refs": refs,
            "evidence_ids": evs,
            "_tool_trace": tool_trace,
            "_aggregated": aggregated,
        }

    discussion_id = state.get("discussion_id", "")
    tool_trace, messages = await _run_tool_loop(
        role, match_id, system_text, outputs, ctx, discussion_id
    )
    return await _finalize_message(role, state, messages, tool_trace)
