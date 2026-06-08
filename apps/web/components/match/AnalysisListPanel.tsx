"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createDiscussionDraft } from "@/lib/api";
import type { DiscussionListItem } from "@/lib/types";
import { formatDateTime } from "@/lib/formatDateTime";

const STATUS: Record<string, { label: string; className: string }> = {
  draft: { label: "未开始", className: "bg-slate-700/80 text-slate-300" },
  pending: { label: "排队中", className: "bg-slate-600/80 text-slate-200" },
  running: { label: "分析中", className: "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/40" },
  awaiting_user: { label: "等待回复", className: "bg-blue-500/20 text-blue-300" },
  completed: { label: "已完成", className: "bg-pitch-500/30 text-pitch-300 ring-1 ring-pitch-400/30" },
  partial: { label: "部分完成", className: "bg-orange-500/20 text-orange-300" },
  failed: { label: "失败", className: "bg-red-500/20 text-red-300" },
  cancelled: { label: "已停止", className: "bg-slate-600/60 text-slate-400" },
};

function statusOf(s: string) {
  return STATUS[s] || { label: s, className: "bg-slate-700 text-slate-300" };
}

export function AnalysisListPanel({
  matchId,
  initialDiscussions,
}: {
  matchId: string;
  initialDiscussions: DiscussionListItem[];
}) {
  const router = useRouter();
  const discussions = initialDiscussions;
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const disc = await createDiscussionDraft(matchId);
      router.push(`/match/${matchId}/analysis/${disc.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
      setCreating(false);
    }
  };

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-100">战术室分析</h2>
          <p className="mt-1 text-sm text-slate-500">
            每场比赛可进行多次独立合议，互不影响
          </p>
        </div>
        <button
          type="button"
          onClick={() => void handleCreate()}
          disabled={creating}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-pitch-500 to-pitch-400 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-pitch-500/20 transition hover:brightness-110 disabled:opacity-60"
        >
          {creating ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              创建中…
            </>
          ) : (
            <>+ 新建分析</>
          )}
        </button>
      </div>

      {error && (
        <p className="mb-4 rounded-lg border border-red-800/50 bg-red-950/30 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {discussions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-pitch-600/80 bg-pitch-900/40 px-6 py-12 text-center">
          <p className="text-slate-300">暂无分析记录</p>
          <p className="mt-2 text-sm text-slate-500">
            点击「新建分析」创建记录，进入后手动开始合议
          </p>
        </div>
      ) : (
        <ul className="space-y-3">
          {discussions.map((d, idx) => {
            const st = statusOf(d.status);
            const title = `分析 #${discussions.length - idx}`;
            const time = d.finished_at || d.started_at;
            return (
              <li key={d.id}>
                <Link
                  href={`/match/${matchId}/analysis/${d.id}`}
                  className="group flex items-center gap-4 rounded-xl border border-pitch-700/80 bg-pitch-800/50 p-4 transition hover:border-pitch-500/60 hover:bg-pitch-800 hover:shadow-md hover:shadow-black/20"
                >
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-pitch-700/60 text-sm font-bold text-pitch-300 ring-1 ring-pitch-600/50">
                    {discussions.length - idx}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-100 group-hover:text-white">
                        {title}
                      </span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${st.className}`}
                      >
                        {st.label}
                      </span>
                      {d.status === "running" && (
                        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
                      )}
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {time ? formatDateTime(time) : "尚未开始"}
                      {d.message_count > 0 ? ` · ${d.message_count} 条消息` : ""}
                      {d.phase ? ` · ${d.phase}` : ""}
                    </p>
                    {d.error_reason && (
                      <p className="mt-1 truncate text-xs text-red-400/80">
                        {d.error_reason}
                      </p>
                    )}
                  </div>
                  <span className="shrink-0 text-slate-600 transition group-hover:translate-x-0.5 group-hover:text-pitch-400">
                    →
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
