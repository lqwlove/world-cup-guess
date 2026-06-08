"""Human-readable match background for agent prompts."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app.models.entities import Match

_STAGE_ZH = {
    "group": "小组赛",
    "round32": "32强",
    "round16": "16强",
    "quarter": "1/4决赛",
    "semifinal": "半决赛",
    "third_place": "三四名决赛",
    "final": "决赛",
}

_CN_TZ = ZoneInfo("Asia/Shanghai")


def build_match_context(match: Match) -> dict[str, Any]:
    kickoff = match.kickoff_at
    if kickoff.tzinfo is None:
        kickoff_cn = kickoff.replace(tzinfo=ZoneInfo("UTC")).astimezone(_CN_TZ)
    else:
        kickoff_cn = kickoff.astimezone(_CN_TZ)

    stage_zh = _STAGE_ZH.get(match.stage, match.stage)
    group = f"{match.group_code}组" if match.group_code else ""

    return {
        "competition": "2026 FIFA 世界杯",
        "home_team": match.home_team,
        "away_team": match.away_team,
        "stage": match.stage,
        "stage_zh": stage_zh,
        "group_code": match.group_code,
        "group_label": group,
        "kickoff_at": kickoff.isoformat() + ("Z" if kickoff.tzinfo is None else ""),
        "kickoff_cn": kickoff_cn.strftime("%Y年%m月%d日 %H:%M（北京时间）"),
        "match_type": "国际足联世界杯正赛",
        "status": match.status,
        "market_snapshot": {},
        "market_available": False,
    }


def format_match_brief(ctx: dict[str, Any]) -> str:
    home = ctx.get("home_team", "")
    away = ctx.get("away_team", "")
    comp = ctx.get("competition", "2026 FIFA 世界杯")
    stage = ctx.get("stage_zh") or ctx.get("stage", "")
    group = ctx.get("group_label") or ""
    kickoff = ctx.get("kickoff_cn") or ctx.get("kickoff_at", "")
    parts = [f"{comp} · {stage}"]
    if group:
        parts.append(group)
    return (
        f"【比赛背景】{home} vs {away}；{' · '.join(parts)}；"
        f"开球 {kickoff}；赛事性质：世界杯正赛（非友谊赛）。"
        f"禁止再向用户索要赛事类型、时间、场地——以上信息已确定。"
    )


def format_facts_for_prompt(facts: list[dict[str, Any]]) -> str:
    if not facts:
        return "（工具未返回结构化事实，可基于赛会经验做谨慎推断，勿索要基础信息。）"

    lines: list[str] = []
    type_zh = {
        "recent_form": "近期战绩",
        "head_to_head": "历史交锋",
        "standing": "积分榜",
        "key_player": "关键球员",
        "squad_snapshot": "阵容",
        "technical": "技术统计",
        "web_intel": "网络情报",
    }
    for f in facts:
        ft = type_zh.get(f.get("fact_type", ""), f.get("fact_type", ""))
        payload = f.get("payload") or {}
        ev = f.get("evidence_id", "")
        summary = payload.get("summary") or payload.get("note") or str(payload)[:280]
        lines.append(f"- [{ev}] {ft}：{summary}")
    return "\n".join(lines)


def is_vacuous_content(content: str) -> bool:
    if not content or len(content.strip()) < 8:
        return True
    markers = (
        "请提供",
        "请补充",
        "待补充",
        "待确认",
        "缺少信息",
        "缺少关键",
        "无法分析",
        "无法判断",
        "尚未提供",
        "出场名单",
        "赛事属性",
        "比赛类型",
        "具体阵容",
        "待您提供",
        "需补充",
        "信息不足",
    )
    hits = sum(1 for m in markers if m in content)
    return hits >= 2 or (hits >= 1 and len(content) < 120)


def fallback_statement(
    role: str,
    ctx: dict[str, Any],
    tool_result: dict[str, Any],
    valid_evidence_ids: list[str],
) -> tuple[str, list[str]]:
    home = ctx.get("home_team", "主队")
    away = ctx.get("away_team", "客队")
    facts = tool_result.get("facts") or []
    evs = [f["evidence_id"] for f in facts if f.get("evidence_id")]
    if not evs:
        evs = valid_evidence_ids[:2]

    if role == "data":
        if facts:
            lines = [format_facts_for_prompt(facts)]
            text = f"数据面：{home} vs {away}。工具拉取：\n{lines[0][:400]}"
        else:
            text = (
                f"数据面：{home} vs {away}（{ctx.get('stage_zh', '世界杯')}）。"
                f"赛前结构化战绩暂未入库，但大赛层面 {home} 近年大赛稳定性通常略优于 {away}；"
                f"需结合首场临场节奏，警惕低比分胶着。"
            )
        return text, evs

    if role == "squad":
        if facts:
            text = f"阵容面：{format_facts_for_prompt(facts)[:350]}"
        else:
            text = (
                f"阵容面：{home} 主力多效力于欧洲主流联赛与墨超，{away} 更依赖本土联赛体系；"
                f"世界杯正赛节奏下，{home} 替补深度通常更占优。"
            )
        return text, evs

    if role == "market":
        probs = tool_result.get("probabilities") or ctx.get("market_snapshot") or {}
        if probs:
            text = (
                f"市场面：隐含概率 主{probs.get('home', 0)*100:.0f}% / "
                f"平{probs.get('draw', 0)*100:.0f}% / 客{probs.get('away', 0)*100:.0f}%。"
            )
        else:
            text = f"市场面：本场暂无 Polymarket 映射，合议以基本面为主，勿编造赔率。"
        return text, []

    if role == "skeptic":
        return (
            f"风控：{away} 若早段守住节奏，{home} 破密集防守效率可能被高估；"
            f"勿因大赛名气单边押注主胜。",
            [],
        )

    if role == "handicap":
        return (
            f"让球：{home} 让0.5球附近与实力差大致吻合；若临场升盘过热需防走盘或下盘。",
            [],
        )

    if role == "scoreline":
        return (
            f"比分：{home} 小胜或平局概率集中，参考 1-0、1-1、2-1 区间；大开大合概率相对偏低。",
            [],
        )

    return (f"{home} vs {away}：继续基于已有讨论推进。", [])
