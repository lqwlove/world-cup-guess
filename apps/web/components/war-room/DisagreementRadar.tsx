"use client";

import type { DiscussionMessage } from "@/lib/types";

/** P2: 四维度争议热度（基于消息类型的简化雷达） */
export function DisagreementRadar({ messages }: { messages: DiscussionMessage[] }) {
  const dims = {
    "1x2": messages.filter((m) => m.role === "data" || m.role === "market").length,
    score: messages.filter((m) => m.role === "scoreline").length,
    handicap: messages.filter((m) => m.role === "handicap").length,
    market: messages.filter((m) => m.msg_type === "CHALLENGE" && m.content.includes("市场")).length,
  };
  const max = Math.max(...Object.values(dims), 1);

  const labels: Record<string, string> = {
    "1x2": "胜平负",
    score: "比分",
    handicap: "让球",
    market: "市场偏差",
  };

  return (
    <div className="mb-4 rounded-lg border border-pitch-700 p-3">
      <h4 className="mb-2 text-xs font-medium text-slate-400">分歧雷达（争议热度）</h4>
      <div className="grid grid-cols-4 gap-2">
        {Object.entries(dims).map(([key, val]) => (
          <div key={key} className="text-center">
            <div className="mx-auto mb-1 h-16 w-8 overflow-hidden rounded bg-pitch-700">
              <div
                className="mt-auto w-full bg-amber-500 transition-all"
                style={{ height: `${(val / max) * 100}%`, marginTop: `${100 - (val / max) * 100}%` }}
              />
            </div>
            <span className="text-xs text-slate-400">{labels[key]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
