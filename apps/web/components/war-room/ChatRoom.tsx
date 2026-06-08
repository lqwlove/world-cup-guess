"use client";

import { useEffect, useMemo, useRef, type ReactNode } from "react";
import type { DiscussionMessage } from "@/lib/types";
import {
  ROLE_LABELS,
  buildClaimIndex,
  claimIdToMessageSeq,
  formatEvidenceLabel,
  formatMessageContent,
  formatMsgTypeLabel,
  formatPhaseLabel,
  formatRefLabel,
} from "@/lib/formatDiscussionMessage";

const ROLE_COLORS: Record<string, string> = {
  moderator: "bg-gold-500/20 text-gold-300",
  skeptic: "bg-red-500/15 text-red-300",
  data: "bg-blue-500/15 text-blue-300",
  market: "bg-purple-500/15 text-purple-300",
  squad: "bg-emerald-500/15 text-emerald-300",
  handicap: "bg-amber-500/15 text-amber-300",
  scoreline: "bg-cyan-500/15 text-cyan-300",
  supervisor: "bg-gold-500/20 text-gold-300",
  user: "bg-slate-600/40 text-slate-100",
  summarizer: "bg-green-500/15 text-green-300",
};

function scrollToMessage(seq: number) {
  document.getElementById(`msg-${seq}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function ChatRoom({
  messages,
  isLive,
  input,
}: {
  messages: DiscussionMessage[];
  isLive?: boolean;
  input?: ReactNode;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const claimIndex = useMemo(() => buildClaimIndex(messages), [messages]);

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
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>{formatMsgTypeLabel(m.msg_type)}</span>
                {m.phase && <span>· {formatPhaseLabel(m.phase)}</span>}
                {m.refs?.map((r) => {
                  const targetSeq = claimIdToMessageSeq(messages, r);
                  const snippet = claimIndex[r];
                  return (
                    <button
                      key={r}
                      type="button"
                      title={snippet ? `「${snippet}」` : "论点编号"}
                      disabled={targetSeq == null}
                      onClick={() => targetSeq != null && scrollToMessage(targetSeq)}
                      className="text-gold-400 hover:underline disabled:cursor-default disabled:no-underline"
                    >
                      {formatRefLabel(r, claimIndex)}
                    </button>
                  );
                })}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">
                {formatMessageContent(m)}
              </p>
              {m.evidence_ids?.length > 0 && (
                <p className="mt-1 text-xs text-slate-500">
                  依据：{m.evidence_ids.map(formatEvidenceLabel).join("；")}
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
      {messages.some((m) => m.refs?.length > 0 || m.evidence_ids?.length > 0) && (
        <p className="border-t border-pitch-800 px-3 py-2 text-xs text-slate-500">
          说明：<span className="text-gold-400/90">论点 E-xxx</span>{" "}
          是会上某条观点的编号，点击可跳到原文；
          <span className="text-slate-400">依据 EV-xxx</span>{" "}
          是数据库里的结构化事实来源。
        </p>
      )}
      {input ? <div className="border-t border-pitch-700 p-3">{input}</div> : null}
    </div>
  );
}
