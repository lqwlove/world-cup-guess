ROLES = ["data", "squad", "market", "skeptic", "handicap", "scoreline", "moderator"]

# Specialists routed by supervisor (moderator merged into supervisor)
SPECIALIST_ROLES = ["data", "squad", "market", "skeptic", "handicap", "scoreline"]

SUPERVISOR_ROLE = "supervisor"

ROLE_LABELS = {
    "data": "数据官",
    "squad": "阵容官",
    "market": "市场官",
    "skeptic": "风控官",
    "handicap": "让球专家",
    "scoreline": "比分专家",
    "moderator": "主持人",
    "supervisor": "调度官",
    "user": "用户",
    "summarizer": "总结官",
}

PHASES = [
    "Opening",
    "CrossExam",
    "DeepDive",
    "PlaybookSplit",
    "FinalVote",
    "Consensus",
    "Analysis",
    "FollowUp",
    "Summary",
]

PHASE_LABELS = {
    "Opening": "开场陈述",
    "CrossExam": "交叉质询",
    "DeepDive": "深度讨论",
    "PlaybookSplit": "玩法分拆",
    "FinalVote": "最终表决",
    "Consensus": "形成共识",
    "Analysis": "分析中",
    "FollowUp": "会后追问",
    "Summary": "总结",
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
    "USER_REPLY",
    "SYSTEM_QUESTION",
]
