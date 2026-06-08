"use client";

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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

const ROLE_AVATAR: Record<string, string> = {
  data: "bg-sky-600/90 text-white",
  squad: "bg-emerald-600/90 text-white",
  market: "bg-violet-600/90 text-white",
  skeptic: "bg-rose-600/90 text-white",
  handicap: "bg-amber-600/90 text-white",
  scoreline: "bg-cyan-600/90 text-white",
  supervisor: "bg-yellow-600/90 text-white",
  summarizer: "bg-green-700/90 text-white",
  user: "bg-slate-500 text-white",
};

const ROLE_SHORT: Record<string, string> = {
  data: "数",
  squad: "阵",
  market: "市",
  skeptic: "风",
  handicap: "盘",
  scoreline: "分",
  supervisor: "调",
  summarizer: "总",
  user: "我",
};

function scrollToMessage(seq: number) {
  document.getElementById(`msg-${seq}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function RoleAvatar({ role }: { role: string }) {
  return (
    <div
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-xs font-semibold shadow-sm ${
        ROLE_AVATAR[role] || "bg-pitch-600 text-slate-200"
      }`}
      title={ROLE_LABELS[role] || role}
    >
      {ROLE_SHORT[role] || role.slice(0, 1).toUpperCase()}
    </div>
  );
}

function CollapsibleToolCall({
  tool,
  args,
  resultPreview,
  defaultOpen = false,
}: {
  tool: string;
  args?: Record<string, unknown>;
  resultPreview?: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const argKeys = args ? Object.keys(args).filter((k) => args[k] != null && args[k] !== "") : [];

  return (
    <div className="rounded-lg border border-pitch-700/50 bg-pitch-950/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-400 transition hover:bg-pitch-800/40"
      >
        <svg
          className={`h-3.5 w-3.5 shrink-0 text-slate-500 transition ${open ? "rotate-90" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path d="M6 4l8 6-8 6V4z" />
        </svg>
        <span className="text-slate-300">调用工具</span>
        <span className="font-medium text-pitch-400">{formatToolLabel(tool)}</span>
      </button>
      {open && (
        <div className="border-t border-pitch-800/80 px-3 py-2 text-xs">
          <p className="text-slate-600">{tool}</p>
          {argKeys.length > 0 && (
            <p className="mt-1.5 text-slate-500">
              参数：{argKeys.map((k) => `${k}=${String(args![k]).slice(0, 80)}`).join("，")}
            </p>
          )}
          {resultPreview && (
            <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/20 p-2 font-mono text-[11px] leading-relaxed text-slate-500">
              {resultPreview}
            </pre>
          )}
        </div>
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
  const [toolsOpen, setToolsOpen] = useState(false);

  return (
    <div className="flex items-start gap-3">
      <RoleAvatar role={role} />
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-pitch-700/60 bg-pitch-800/80 px-3.5 py-2.5">
        <div className="flex items-center gap-2 text-sm text-slate-300">
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-pitch-400/30 border-t-pitch-400" />
          <span>{ROLE_LABELS[role] || role} 正在分析…</span>
        </div>
        {liveToolCalls.length > 0 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setToolsOpen((v) => !v)}
              className="text-xs text-slate-500 hover:text-slate-400"
            >
              {toolsOpen ? "收起" : "展开"}工具调用（{liveToolCalls.length}）
            </button>
            {toolsOpen && (
              <div className="mt-2 space-y-1.5">
                {liveToolCalls.map((tc, i) => (
                  <CollapsibleToolCall
                    key={`${tc.tool}-${tc.index ?? i}`}
                    tool={tc.tool}
                    args={tc.args}
                    resultPreview={tc.result_preview}
                  />
                ))}
              </div>
            )}
          </div>
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
  emptyHint,
}: {
  messages: DiscussionMessage[];
  isLive?: boolean;
  analyzingRole?: string | null;
  liveToolCalls?: LiveToolCall[];
  input?: ReactNode;
  emptyHint?: ReactNode;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const claimIndex = useMemo(() => buildClaimIndex(messages), [messages]);
  const showAnalyzing = Boolean(analyzingRole);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLive, showAnalyzing, liveToolCalls.length]);

  const showEmpty = messages.length === 0 && !isLive && !showAnalyzing;

  return (
    <div className="overflow-hidden rounded-2xl border border-pitch-700/70 bg-pitch-900/30 shadow-sm">
      <div className="flex items-center justify-between border-b border-pitch-800/80 px-4 py-3">
        <span className="text-sm font-medium text-slate-200">战术室群聊</span>
        {isLive && (
          <span className="flex items-center gap-1.5 text-xs text-amber-400/90">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
            进行中
          </span>
        )}
      </div>

      <div className="max-h-[28rem] space-y-4 overflow-y-auto px-4 py-4">
        {showEmpty && (
          emptyHint || (
            <p className="py-8 text-center text-sm text-slate-500">暂无讨论记录</p>
          )
        )}

        {messages.map((m) => {
          if (m.msg_type === "TOOL_CALL") {
            const tc = parseToolCallContent(m.content);
            if (!tc) return null;
            return (
              <div key={m.seq} id={`msg-${m.seq}`} className="ml-12">
                <CollapsibleToolCall
                  tool={tc.tool}
                  args={tc.args}
                  resultPreview={tc.result_preview}
                />
              </div>
            );
          }

          return (
            <div key={m.seq} id={`msg-${m.seq}`} className="flex items-start gap-3">
              <RoleAvatar role={m.role} />
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span className="text-sm font-medium text-slate-200">
                    {ROLE_LABELS[m.role] || m.role}
                  </span>
                  <span className="text-xs text-slate-500">
                    {formatMsgTypeLabel(m.msg_type)}
                    {m.phase ? ` · ${formatPhaseLabel(m.phase)}` : ""}
                  </span>
                </div>
                <div className="rounded-2xl rounded-tl-md bg-pitch-800/90 px-3.5 py-2.5 text-sm leading-relaxed text-slate-100 shadow-sm">
                  <p className="whitespace-pre-wrap">{formatMessageContent(m)}</p>
                  {m.refs?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5 border-t border-pitch-700/50 pt-2">
                      {m.refs.map((r) => {
                        const targetSeq = claimIdToMessageSeq(messages, r);
                        return (
                          <button
                            key={r}
                            type="button"
                            disabled={targetSeq == null}
                            onClick={() => targetSeq != null && scrollToMessage(targetSeq)}
                            className="rounded bg-pitch-900/60 px-1.5 py-0.5 text-xs text-gold-400/90 hover:underline disabled:cursor-default"
                          >
                            {formatRefLabel(r, claimIndex)}
                          </button>
                        );
                      })}
                    </div>
                  )}
                  {m.evidence_ids?.length > 0 && (
                    <p className="mt-2 border-t border-pitch-700/50 pt-2 text-xs text-slate-500">
                      依据 {m.evidence_ids.map(formatEvidenceLabel).join(" · ")}
                    </p>
                  )}
                </div>
              </div>
            </div>
          );
        })}

        {showAnalyzing && analyzingRole && (
          <AnalyzingIndicator role={analyzingRole} liveToolCalls={liveToolCalls} />
        )}

        <div ref={bottomRef} />
      </div>

      {input ? <div className="border-t border-pitch-800/80 bg-pitch-950/30 px-4 py-3">{input}</div> : null}
    </div>
  );
}
