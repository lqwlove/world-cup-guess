"use client";

import { useMemo, useState } from "react";
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

const MSG_STYLES: Record<string, string> = {
  STATEMENT: "border-l-pitch-400",
  CHALLENGE: "border-l-red-500",
  REBUTTAL: "border-l-amber-500",
  SUPPORT: "border-l-blue-400",
  VOTE: "border-l-gold-400",
  ACK: "border-l-green-500",
  ACK_WITH_RESERVATION: "border-l-orange-500",
  CONSENSUS_FINAL: "border-l-gold-500 bg-gold-500/10",
  THREAD_DIGEST: "border-l-slate-500 opacity-80",
};

const PHASE_ORDER = [
  "Analysis",
  "Opening",
  "CrossExam",
  "DeepDive",
  "PlaybookSplit",
  "FinalVote",
  "Summary",
  "FollowUp",
  "Consensus",
];

function scrollToMessage(seq: number) {
  document.getElementById(`msg-${seq}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function MessageTimeline({
  messages,
  readMode,
}: {
  messages: DiscussionMessage[];
  readMode: "consensus" | "full" | "disagreement";
}) {
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const claimIndex = useMemo(() => buildClaimIndex(messages), [messages]);

  const filtered = useMemo(() => {
    if (readMode === "disagreement") {
      return messages.filter((m) =>
        ["CHALLENGE", "REBUTTAL", "ACK_WITH_RESERVATION"].includes(m.msg_type),
      );
    }
    if (readMode === "consensus") {
      return messages.filter((m) =>
        ["CONSENSUS_FINAL", "CONSENSUS_DRAFT", "ACK", "ACK_WITH_RESERVATION"].includes(
          m.msg_type,
        ),
      );
    }
    return messages;
  }, [messages, readMode]);

  const byPhase = useMemo(() => {
    const map: Record<string, DiscussionMessage[]> = {};
    for (const m of filtered) {
      const p = m.phase || "Other";
      if (!map[p]) map[p] = [];
      map[p].push(m);
    }
    return map;
  }, [filtered]);

  const phases = [
    ...PHASE_ORDER.filter((p) => byPhase[p]),
    ...Object.keys(byPhase).filter((p) => !PHASE_ORDER.includes(p)),
  ];

  if (filtered.length === 0) {
    return <p className="text-sm text-slate-400">暂无讨论消息</p>;
  }

  return (
    <div className="space-y-3">
      {phases.map((phase) => {
        const isCollapsed = collapsed[phase] ?? readMode === "consensus";
        return (
          <div key={phase} className="rounded-lg border border-pitch-700">
            <button
              type="button"
              className="flex w-full items-center justify-between px-3 py-2 text-left text-sm font-medium text-slate-300"
              onClick={() => setCollapsed((c) => ({ ...c, [phase]: !isCollapsed }))}
            >
              <span>{formatPhaseLabel(phase)}</span>
              <span className="text-xs text-slate-500">{byPhase[phase].length} 条</span>
            </button>
            {!isCollapsed && (
              <div className="space-y-2 border-t border-pitch-700 p-2">
                {byPhase[phase].map((m) => (
                  <div
                    key={m.seq}
                    id={`msg-${m.seq}`}
                    className={`rounded border-l-4 bg-pitch-900/50 px-3 py-2 ${MSG_STYLES[m.msg_type] || "border-l-slate-600"}`}
                  >
                    <div className="mb-1 flex flex-wrap gap-2 text-xs">
                      <span className="font-medium text-pitch-400">
                        {ROLE_LABELS[m.role] || m.role}
                      </span>
                      <span className="text-slate-500">{formatMsgTypeLabel(m.msg_type)}</span>
                      {m.refs?.map((r) => {
                        const targetSeq = claimIdToMessageSeq(messages, r);
                        return (
                          <button
                            key={r}
                            type="button"
                            title={claimIndex[r]}
                            disabled={targetSeq == null}
                            onClick={() => targetSeq != null && scrollToMessage(targetSeq)}
                            className="text-gold-400 hover:underline disabled:cursor-default"
                          >
                            {formatRefLabel(r, claimIndex)}
                          </button>
                        );
                      })}
                    </div>
                    <p className="text-sm leading-relaxed">{formatMessageContent(m)}</p>
                    {m.evidence_ids?.length > 0 && (
                      <p className="mt-1 text-xs text-slate-500">
                        依据：{m.evidence_ids.map(formatEvidenceLabel).join("；")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
