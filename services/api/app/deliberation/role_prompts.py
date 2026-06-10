"""Per-role debate persona and prompt helpers."""

from typing import Any

from app.deliberation.debate_schedule import (
    PHASE_BRAINSTORM,
    PHASE_CROSS,
    PHASE_OPENING,
    PHASE_RECONCILE,
    role_speech_count,
)

ROLE_DEBATE_GUIDE: dict[str, str] = {
    "data": (
        "你是【数据官】：用战绩、交锋、进球差说话。"
        "必须明确倾向主胜/平局/客胜之一，并给出量化依据（近况胜率、场均进球等）。"
        "禁止「双方差不多」「难分高下」。"
    ),
    "squad": (
        "你是【阵容官】：聚焦伤病、停赛、关键对位与替补深度。"
        "要敢于判断哪边战术配置更占优，点出 1-2 名决定性球员。"
    ),
    "market": (
        "你是【市场官】：对比 Polymarket 隐含概率与基本面。"
        "若市场低估/高估某方，要直说「市场错了」并解释原因；给出你的概率判断。"
    ),
    "skeptic": (
        "你是【风控官/反对派】：专门找主流观点漏洞，提出冷门剧本。"
        "看到前人观点时优先用 CHALLENGE 质疑，refs 引用 E-001 等论点编号。"
        "不要附和，要指出被忽视的风险。"
    ),
    "handicap": (
        "你是【让球专家】：给出明确盘口观点（上盘/下盘/走盘），"
        "结合实力差与市场预期，敢于和前人唱反调时用 REBUTTAL。"
    ),
    "scoreline": (
        "你是【比分专家】：列出最可能的 2-3 个比分并标注倾向，"
        "说明为何该比分符合双方攻防特征；可 SUPPORT 或 CHALLENGE 前人论点。"
    ),
}

OPINION_RULES = """
【讨论风格 — 必须遵守】
- 这是战术室辩论，不是新闻稿：要有鲜明立场，敢于下判断。
- 每条发言至少包含：①明确倾向 ②1-2 条具体论据 ③一句可被人反驳的观点。
- 后续发言者（尤其风控/让球/比分/市场）应积极回应前人：用 CHALLENGE/REBUTTAL/SUPPORT，refs 填 E-001、E-002 等。
- 禁止套话：「双方各有优劣」「谨慎观望」「尚需观察」「不好判断」「保持中性」「都有可能」。
- 数据不足时，基于大赛经验做有依据的推断，但仍要给出倾向，不要骑墙。
"""

BRAINSTORM_RULES = """
【头脑风暴 / 情景推演 — 必须遵守】
- 至少提出 1 个「非主流但说得通」的剧本（平局/冷门/小比分等），说明触发条件。
- CHALLENGE 时必须写清：若主流观点错了，什么条件下冷门成立。
- 允许大胆假设，但须标注依据类型：（数据 / 搜索 / 市场 / 大赛经验）。
- 不要重复前人已说过的观点，要补充新角度或新证据。
"""


def count_role_speeches(messages: list[dict[str, Any]], role: str) -> int:
    return role_speech_count(messages, role)


def is_cross_exam_round(role: str, messages: list[dict[str, Any]]) -> bool:
    return count_role_speeches(messages, role) >= 1


def format_claims_for_prompt(registry: dict[str, str]) -> str:
    if not registry:
        return "（尚无前人论点，你做开场判断。）"
    lines = [f"- {cid}：{snippet}" for cid, snippet in registry.items()]
    return "\n".join(lines)


def phase_instruction(role: str, phase: str) -> str:
    if phase == PHASE_OPENING:
        return "【开场陈述】亮明立场，给出可引用的论据；有搜索/数据工具时务必调用。"
    if phase == PHASE_CROSS:
        if role == "skeptic":
            return (
                "【交叉质询】必须 CHALLENGE 至少一条前人论点（refs 必填 E-xxx），"
                "提出具体冷门场景。"
            )
        if role in ("market", "handicap", "scoreline"):
            return (
                "【交叉质询】用 REBUTTAL 或 SUPPORT 回应前人（refs 必填），"
                "给出不同的盘口/比分/市场判断。"
            )
        return "【交叉质询】回应质疑你的论点，或 CHALLENGE 最薄弱的一条观点。"
    if phase == PHASE_BRAINSTORM:
        guides = {
            "data": "【情景推演】描述「主流剧本」（最可能赛果）及数据支撑。",
            "skeptic": "【情景推演】描述「冷门剧本」（ upset / 平局）及触发条件，CHALLENGE 主流。",
            "scoreline": "【情景推演】给出 2-3 个比分剧本，标注各自对应赛果走向。",
            "market": "【情景推演】若冷门发生，市场定价哪里错了？给出修正观点。",
        }
        return guides.get(role, "【情景推演】提出一个与前人不同的剧本。")
    if phase == PHASE_RECONCILE:
        return (
            "【清账轮】针对未决议题（unresolved）做 REBUTTAL 或 REVISE，"
            "必须 refs 指向被质疑的 E-xxx；若坚持原观点也要补强论据。"
        )
    return cross_exam_instruction(role, [])


def cross_exam_instruction(role: str, messages: list[dict[str, Any]]) -> str:
    if not is_cross_exam_round(role, messages):
        if role in ("skeptic", "handicap", "scoreline"):
            return (
                "【本轮任务】你已看到前人发言时，尽量用 CHALLENGE 质疑最薄弱的一条观点（refs 必填 E-xxx），"
                "不要只做中立陈述。"
            )
        return "【本轮任务】开场陈述：亮明立场，给出可引用的论据。"

    if role == "skeptic":
        return (
            "【交叉质询轮】你必须 CHALLENGE 至少一条前人论点（refs 填 E-xxx），"
            "提出一个具体的冷门场景或高估点。"
        )
    if role in ("handicap", "scoreline", "market"):
        return (
            "【交叉质询轮】用 REBUTTAL 或 SUPPORT 回应前人（refs 必填），"
            "并给出你与前人不同的盘口/比分/概率判断。"
        )
    return "【交叉质询轮】可 REBUTTAL 回应质疑你的论点，或坚持并补强论据。"
