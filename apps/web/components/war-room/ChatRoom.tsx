"use client";

import { useEffect, useRef } from "react";
import type { DiscussionMessage } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  data: "数据官",
  squad: "阵容官",
  market: "市场官",
  skeptic: "风控官",
  handicap: "让球专家",
  scoreline: "比分专家",
  moderator: "主持人",
};

const MSG_LABELS: Record<string, string> = {
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
};

const ROLE_COLORS: Record<string, string> = {
  moderator: "bg-gold-500/20 text-gold-300",
  skeptic: "bg-red-500/15 text-red-300",
  data: "bg-blue-500/15 text-blue-300",
  market: "bg-purple-500/15 text-purple-300",
  squad: "bg-emerald-500/15 text-emerald-300",
  handicap: "bg-amber-500/15 text-amber-300",
  scoreline: "bg-cyan-500/15 text-cyan-300",
};

export function ChatRoom({
  messages,
  isLive,
}: {
  messages: DiscussionMessage[];
  isLive?: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLive]);

  if (messages.length === 0 && !isLive) {
    return (
      <p className="rounded-lg border border-dashed border-pitch-600 p-4 text-center text-sm text-slate-500">
        暂无讨论记录
      </p>
    );
  }

  return (
    <div className="rounded-xl border border-pitch-700 bg-pitch-900/40">
      <div className="flex items-center justify-between border-b border-pitch-700 px-3 py-2">
        <span className="text-sm font-medium text-slate-300">战术室群聊</span>
        {isLive && (
          <span className="flex items-center gap-1 text-xs text-amber-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-amber-400" />
            合议进行中…
          </span>
        )}
      </div>
      <div className="max-h-[28rem] space-y-3 overflow-y-auto p-3">
        {messages.map((m) => (
          <div key={m.seq} id={`msg-${m.seq}`} className="flex gap-2">
            <div
              className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                ROLE_COLORS[m.role] || "bg-pitch-700 text-slate-300"
              }`}
            >
              {ROLE_LABELS[m.role] || m.role}
            </div>
            <div className="min-w-0 flex-1 rounded-lg bg-pitch-800 px-3 py-2">
              <div className="mb-1 flex flex-wrap gap-2 text-xs text-slate-500">
                <span>{MSG_LABELS[m.msg_type] || m.msg_type}</span>
                {m.phase && <span>· {m.phase}</span>}
                {m.refs?.map((r) => (
                  <span key={r} className="text-gold-400">
                    {r}
                  </span>
                ))}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">
                {m.content}
              </p>
              {m.evidence_ids?.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">
                  证据：{m.evidence_ids.join("、")}
                </p>
              )}
            </div>
          </div>
        ))}
        {isLive && messages.length === 0 && (
          <p className="text-center text-sm text-slate-500">等待各角色发言…</p>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
