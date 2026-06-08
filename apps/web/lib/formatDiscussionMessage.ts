import type { DiscussionMessage } from "./types";

export const PHASE_LABELS: Record<string, string> = {
  Opening: "开场陈述",
  CrossExam: "交叉质询",
  DeepDive: "深度讨论",
  PlaybookSplit: "玩法分拆",
  FinalVote: "最终表决",
  Consensus: "形成共识",
  Analysis: "分析中",
  FollowUp: "会后追问",
  Summary: "总结",
  Other: "其他",
};

export const MSG_TYPE_LABELS: Record<string, string> = {
  STATEMENT: "陈述",
  CHALLENGE: "质疑",
  REBUTTAL: "回应",
  SUPPORT: "支持",
  VOTE: "投票",
  ACK: "确认",
  ACK_WITH_RESERVATION: "保留确认",
  CONSENSUS_FINAL: "共识定稿",
  CONSENSUS_DRAFT: "共识草案",
  THREAD_DIGEST: "阶段摘要",
  REVISE: "修订",
  USER_REPLY: "回复",
  SYSTEM_QUESTION: "提问",
  QUESTION: "提问",
};

export const ROLE_LABELS: Record<string, string> = {
  data: "数据官",
  squad: "阵容官",
  market: "市场官",
  skeptic: "风控官",
  handicap: "让球专家",
  scoreline: "比分专家",
  moderator: "主持人",
  supervisor: "调度官",
  user: "你",
  summarizer: "总结官",
};

const PICK_LABELS: Record<string, string> = {
  home: "主胜",
  draw: "平局",
  away: "客胜",
};

const KNOWN_EN_LINES: Record<string, string> = {
  "Final vote opened for 1x2.": "主持人宣布：胜平负玩法开始表决。",
};

/** 按发言顺序重建论点编号 → 摘要（对应合议里的 E-001、E-002…） */
export function buildClaimIndex(
  messages: DiscussionMessage[],
): Record<string, string> {
  const index: Record<string, string> = {};
  let claimIdx = 0;
  for (const m of messages) {
    if (m.msg_type === "STATEMENT" && m.content.trim()) {
      claimIdx += 1;
      const id = `E-${String(claimIdx).padStart(3, "0")}`;
      const snippet = m.content.trim();
      index[id] =
        snippet.length > 72 ? `${snippet.slice(0, 72)}…` : snippet;
    }
  }
  return index;
}

/** 论点编号对应的消息 seq，用于点击跳转 */
export function claimIdToMessageSeq(
  messages: DiscussionMessage[],
  claimId: string,
): number | null {
  const num = parseInt(claimId.replace(/^E-0*/, ""), 10);
  if (!num || Number.isNaN(num)) return null;
  let count = 0;
  for (const m of messages) {
    if (m.msg_type === "STATEMENT" && m.content.trim()) {
      count += 1;
      if (count === num) return m.seq;
    }
  }
  return null;
}

function formatVoteJson(content: string): string | null {
  try {
    const v = JSON.parse(content) as {
      pick?: string;
      p_low?: number;
      p_high?: number;
      confidence?: number;
    };
    if (!v || typeof v.pick !== "string") return null;
    const pick = PICK_LABELS[v.pick] || v.pick;
    const low = Math.round((v.p_low ?? v.confidence ?? 0.5) * 100);
    const high = Math.round((v.p_high ?? v.confidence ?? 0.5) * 100);
    if (v.p_low != null && v.p_high != null) {
      return `我投「${pick}」，主观概率约 ${low}%～${high}%`;
    }
    return `我投「${pick}」`;
  } catch {
    return null;
  }
}

export function formatMessageContent(m: DiscussionMessage): string {
  if (m.msg_type === "VOTE") {
    const formatted = formatVoteJson(m.content);
    if (formatted) return formatted;
  }
  const trimmed = m.content.trim();
  return KNOWN_EN_LINES[trimmed] ?? m.content;
}

export function formatPhaseLabel(phase: string): string {
  return PHASE_LABELS[phase] || phase;
}

export function formatMsgTypeLabel(msgType: string): string {
  return MSG_TYPE_LABELS[msgType] || msgType;
}

export function formatRefLabel(
  ref: string,
  claimIndex: Record<string, string>,
): string {
  if (/^E-\d+$/i.test(ref)) {
    const snippet = claimIndex[ref];
    return snippet ? `论点 ${ref}` : ref;
  }
  return ref;
}

export function formatEvidenceLabel(id: string): string {
  if (id.includes("form")) return `近况数据（${id}）`;
  if (id.includes("h2h")) return `交锋记录（${id}）`;
  if (id.includes("player")) return `球员情报（${id}）`;
  if (id.includes("elo") || id.includes("technical")) return `技术统计（${id}）`;
  if (id.includes("standing")) return `积分榜（${id}）`;
  return `结构化事实（${id}）`;
}
