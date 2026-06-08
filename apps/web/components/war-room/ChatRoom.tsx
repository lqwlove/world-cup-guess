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
  formatToolLabel,
  parseToolCallContent,
} from "@/lib/formatDiscussionMessage";

export interface LiveToolCall {
  tool: string;
  args?: Record<string, unknown>;
  result_preview?: string;
  index?: number;
}

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

function ToolCallCard({
  tool,
  args,
  resultPreview,
  compact,
}: {
  tool: string;
  args?: Record<string, unknown>;
  resultPreview?: string;
  compact?: boolean;
}) {
  const argKeys = args ? Object.keys(args).filter((k) => args[k] != null && args[k] !== "") : [];
  return (
    <div
      className={`rounded-md border border-pitch-600/80 bg-pitch-950/50 ${
        compact ? "px-2 py-1.5" : "px-2.5 py-2"
      }`}
    >
      <div className="flex items-center gap-1.5 text-xs text-slate-400">
        <span className="text-pitch-400">⚙</span>
        <span className="font-medium text-slate-300">{formatToolLabel(tool)}</span>
        <span className="text-slate-600">({tool})</span>
      </div>
      {argKeys.length > 0 && (
        <p className="mt-1 text-xs text-slate-500">
          参数：{argKeys.map((k) => `${k}=${String(args![k]).slice(0, 60)}`).join("，")}
        </p>
      )}
      {resultPreview && (
        <p className="mt-1 line-clamp-3 font-mono text-[11px] leading-relaxed text-slate-500">
          {resultPreview}
        </p>
      )}
    </div>
  );
}

function AnalyzingIndicator({
  role,
  liveToolCalls,
}: {
  role: string;
  liveToolCalls: LiveToolCall[];
}) {
  return (
    <div className="flex gap-2">
      <div
        className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
          ROLE_COLORS[role] || "bg-pitch-700 text-slate-300"
        }`}
      >
        {ROLE_LABELS[role] || role}
      </div>
      <div className="min-w-0 flex-1 rounded-lg border border-dashed border-pitch-600 bg-pitch-800/60 px-3 py-2">
        <div className="mb-2 flex items-center gap-2 text-sm text-slate-300">
          <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-pitch-500 border-t-transparent" />
          正在分析…
        </div>
        {liveToolCalls.length > 0 ? (
          <div className="space-y-1.5">
            {liveToolCalls.map((tc, i) => (
              <ToolCallCard
                key={`${tc.tool}-${tc.index ?? i}`}
                tool={tc.tool}
                args={tc.args}
                resultPreview={tc.result_preview}
                compact
              />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500">正在调用工具获取数据…</p>
        )}
      </div>
    </div>
  );
}

export function ChatRoom({
  messages,
  isLive,
  analyzingRole,
  liveToolCalls = [],
  input,
}: {
  messages: DiscussionMessage[];
  isLive?: boolean;
  analyzingRole?: string | null;
  liveToolCalls?: LiveToolCall[];
  input?: ReactNode;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const claimIndex = useMemo(() => buildClaimIndex(messages), [messages]);
  const showAnalyzing = Boolean(analyzingRole);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLive, showAnalyzing, liveToolCalls.length]);

  if (messages.length === 0 && !isLive && !showAnalyzing) {
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
        {messages.map((m) => {
          if (m.msg_type === "TOOL_CALL") {
            const tc = parseToolCallContent(m.content);
            if (!tc) return null;
            return (
              <div key={m.seq} id={`msg-${m.seq}`} className="flex gap-2 pl-1">
                <div
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium opacity-70 ${
                    ROLE_COLORS[m.role] || "bg-pitch-700 text-slate-300"
                  }`}
                >
                  {ROLE_LABELS[m.role] || m.role}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="mb-1 text-[11px] text-slate-600">{formatMsgTypeLabel(m.msg_type)}</p>
                  <ToolCallCard
                    tool={tc.tool}
                    args={tc.args}
                    resultPreview={tc.result_preview}
                    compact
                  />
                </div>
              </div>
            );
          }

          return (
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
          );
        })}
        {showAnalyzing && analyzingRole && (
          <AnalyzingIndicator role={analyzingRole} liveToolCalls={liveToolCalls} />
        )}
        {isLive && messages.length === 0 && !showAnalyzing && (
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
