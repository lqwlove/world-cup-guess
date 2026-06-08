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
        return "（工具未返回结构化事实，可基于大赛经验做有依据推断并亮明倾向，勿索要基础信息。）"

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


def is_neutral_content(content: str) -> bool:
    """Detect hedge/neutral phrasing that should be rewritten."""
    if not content:
        return False
    neutral_markers = (
        "双方各有",
        "各有优劣",
        "难分高下",
        "不好判断",
        "谨慎观望",
        "尚需观察",
        "保持中性",
        "都有可能",
        "说不准",
        "不宜贸然",
        "相对均衡",
        "差距不大",
        "拭目以待",
    )
    return any(m in content for m in neutral_markers)


def _last_claim_ref(registry: dict[str, str]) -> list[str]:
    if not registry:
        return []
    keys = sorted(registry.keys())
    return [keys[-1]] if keys else []


def fallback_statement(
    role: str,
    ctx: dict[str, Any],
    tool_result: dict[str, Any],
    valid_evidence_ids: list[str],
    messages: list[dict[str, Any]] | None = None,
    claims_registry: dict[str, str] | None = None,
) -> tuple[str, list[str], str, list[str]]:
    home = ctx.get("home_team", "主队")
    away = ctx.get("away_team", "客队")
    facts = tool_result.get("facts") or []
    evs = [f["evidence_id"] for f in facts if f.get("evidence_id")]
    if not evs:
        evs = valid_evidence_ids[:2]
    registry = claims_registry or {}
    refs = _last_claim_ref(registry)
    has_prior = bool(registry)
    msg_type = "STATEMENT"
    refs_out: list[str] = []

    if role == "data":
        if facts:
            lines = [format_facts_for_prompt(facts)]
            text = (
                f"我倾向【{home}不败】：数据面 {home} vs {away}，"
                f"近况与交锋支持主队控场；客队在高压下进球效率存疑。\n{lines[0][:280]}"
            )
        else:
            text = (
                f"我押【{home}小胜】：大赛经验与阵容厚度上 {home} 明显占优，"
                f"{away} 首战更可能守势，但破密集防守效率决定是 1-0 还是 2-1。"
            )
        return text, evs, msg_type, refs_out

    if role == "squad":
        if facts:
            text = (
                f"阵容上我看好【{home}】：关键对位与替补深度占优。"
                f"{format_facts_for_prompt(facts)[:280]}"
            )
        else:
            text = (
                f"我站【{home}】：主力多在欧洲/墨超体系，轮换质量高于 {away}；"
                f"若 {away} 核心中场受限，下半场体能会是致命短板。"
            )
        return text, evs, msg_type, refs_out

    if role == "market":
        probs = tool_result.get("probabilities") or ctx.get("market_snapshot") or {}
        if probs:
            h, d, a = probs.get("home", 0), probs.get("draw", 0), probs.get("away", 0)
            lean = home if h >= max(d, a) else (away if a >= d else "平局")
            text = (
                f"市场隐含 主{h*100:.0f}%/平{d*100:.0f}%/客{a*100:.0f}%，"
                f"我认为市场对【{lean}】定价{'偏保守' if lean == home else '有偏差'}——"
                f"基本面与赔率存在可博弈空间。"
            )
        else:
            text = (
                f"暂无 Polymarket 映射，但我仍倾向【{home}】："
                f"名气与大赛履历已被市场习惯性高估客队爆冷概率。"
            )
        return text, [], msg_type, refs_out

    if role == "skeptic":
        msg_type = "CHALLENGE" if has_prior else "STATEMENT"
        refs_out = refs if has_prior else []
        text = (
            f"我反对一边倒看好【{home}】：{away} 若收缩防线+快速转换，"
            f"{home} 进攻效率可能被高估；冷门比分 0-0/1-1 不应被忽视。"
        )
        return text, [], msg_type, refs_out

    if role == "handicap":
        if has_prior:
            msg_type = "REBUTTAL"
            refs_out = refs
        text = (
            f"盘口我选【{home} -0.5 上盘】：实力差支撑让半球，"
            f"但若风控说的胶着成立，走盘风险集中在 1-0 小胜。"
        )
        return text, [], msg_type, refs_out

    if role == "scoreline":
        if has_prior:
            msg_type = "SUPPORT"
            refs_out = refs[:1]
        text = (
            f"比分我押【2-1、1-0】优先，次选【1-1】：{home} 控场但未必大胜，"
            f"{away} 有反击偷一个球的空间。"
        )
        return text, [], msg_type, refs_out

    return (f"{home} vs {away}：我倾向主队方向，继续辩论。", [], "STATEMENT", [])
