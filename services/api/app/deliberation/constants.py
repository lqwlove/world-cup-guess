ROLES = ["data", "squad", "market", "skeptic", "handicap", "scoreline", "moderator"]

ROLE_LABELS = {
    "data": "数据官",
    "squad": "阵容官",
    "market": "市场官",
    "skeptic": "风控官",
    "handicap": "让球专家",
    "scoreline": "比分专家",
    "moderator": "主持人",
}

PHASES = [
    "Opening",
    "CrossExam",
    "DeepDive",
    "PlaybookSplit",
    "FinalVote",
    "Consensus",
]

PHASE_LABELS = {
    "Opening": "开场陈述",
    "CrossExam": "交叉质询",
    "DeepDive": "深度讨论",
    "PlaybookSplit": "玩法分拆",
    "FinalVote": "最终表决",
    "Consensus": "形成共识",
}

MSG_TYPES = [
    "STATEMENT",
    "CHALLENGE",
    "REBUTTAL",
    "REVISE",
    "SUPPORT",
    "QUESTION",
    "VOTE",
    "ACK",
    "ACK_WITH_RESERVATION",
    "CONSENSUS_DRAFT",
    "CONSENSUS_FINAL",
    "THREAD_DIGEST",
]
