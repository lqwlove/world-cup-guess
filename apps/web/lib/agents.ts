export type AgentRole =
  | "supervisor"
  | "data"
  | "squad"
  | "market"
  | "skeptic"
  | "handicap"
  | "scoreline"
  | "summarizer";

export interface AgentPersona {
  role: AgentRole;
  label: string;
  short: string;
  emoji: string;
  tagline: string;
  avatarClass: string;
  ringClass: string;
}

export const AGENT_PERSONAS: AgentPersona[] = [
  {
    role: "supervisor",
    label: "调度官",
    short: "调",
    emoji: "🎯",
    tagline: "编排辩论节奏，推动交叉质询",
    avatarClass: "bg-gradient-to-br from-amber-400 to-yellow-600",
    ringClass: "ring-amber-400/50",
  },
  {
    role: "data",
    label: "数据官",
    short: "数",
    emoji: "📊",
    tagline: "战绩、交锋、进球差量化推演",
    avatarClass: "bg-gradient-to-br from-sky-400 to-blue-600",
    ringClass: "ring-sky-400/50",
  },
  {
    role: "squad",
    label: "阵容官",
    short: "阵",
    emoji: "⚔️",
    tagline: "伤病停赛与关键对位拆解",
    avatarClass: "bg-gradient-to-br from-emerald-400 to-green-600",
    ringClass: "ring-emerald-400/50",
  },
  {
    role: "market",
    label: "市场官",
    short: "市",
    emoji: "📈",
    tagline: "Polymarket 隐含概率 vs 基本面",
    avatarClass: "bg-gradient-to-br from-violet-400 to-purple-600",
    ringClass: "ring-violet-400/50",
  },
  {
    role: "skeptic",
    label: "风控官",
    short: "风",
    emoji: "🛡️",
    tagline: "专找漏洞，提出冷门剧本",
    avatarClass: "bg-gradient-to-br from-rose-400 to-red-600",
    ringClass: "ring-rose-400/50",
  },
  {
    role: "handicap",
    label: "让球专家",
    short: "盘",
    emoji: "🎲",
    tagline: "盘口上盘下盘，敢于唱反调",
    avatarClass: "bg-gradient-to-br from-orange-400 to-amber-600",
    ringClass: "ring-orange-400/50",
  },
  {
    role: "scoreline",
    label: "比分专家",
    short: "分",
    emoji: "⚽",
    tagline: "最可能比分与攻防节奏",
    avatarClass: "bg-gradient-to-br from-cyan-400 to-teal-600",
    ringClass: "ring-cyan-400/50",
  },
  {
    role: "summarizer",
    label: "总结官",
    short: "总",
    emoji: "✅",
    tagline: "汇总裁决，输出明确结论",
    avatarClass: "bg-gradient-to-br from-pitch-400 to-green-700",
    ringClass: "ring-pitch-400/50",
  },
];

export const AGENT_BY_ROLE = Object.fromEntries(
  AGENT_PERSONAS.map((a) => [a.role, a]),
) as Record<AgentRole, AgentPersona>;

export interface DemoChatMessage {
  role: AgentRole;
  msgType: string;
  text: string;
}

export const DEMO_BRAINSTORM: DemoChatMessage[] = [
  {
    role: "supervisor",
    msgType: "开场",
    text: "巴西 vs 阿根廷 — 诸位专家，请亮明立场，允许激烈辩论。",
  },
  {
    role: "data",
    msgType: "陈述",
    text: "近 10 场主场胜率 65%，场均进球 2.1，数据面倾向主胜。",
  },
  {
    role: "squad",
    msgType: "陈述",
    text: "核心前锋伤愈复出，左路对位是本场破局关键。",
  },
  {
    role: "market",
    msgType: "陈述",
    text: "Polymarket 主胜仅 42%，市场明显低估了主队。",
  },
  {
    role: "skeptic",
    msgType: "质疑",
    text: "CHALLENGE @E-002：大赛淘汰赛的心理压力，你们算进去了吗？",
  },
  {
    role: "handicap",
    msgType: "回应",
    text: "REBUTTAL — 盘口 -0.5 低水，上盘仍值得跟进。",
  },
  {
    role: "scoreline",
    msgType: "陈述",
    text: "最可能比分 2-1、1-1，攻防节奏会拖入下半场。",
  },
  {
    role: "summarizer",
    msgType: "结论",
    text: "合议结论：主胜 · 参考比分 2-1",
  },
];
