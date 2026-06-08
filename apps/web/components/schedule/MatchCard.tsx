import Link from "next/link";
import type { Match } from "@/lib/types";
import { formatKickoff } from "@/lib/formatDateTime";
import { stageLabel } from "@/lib/stageLabels";

const STATUS_LABELS: Record<string, string> = {
  none: "未分析",
  generating: "分析中",
  ready: "有分析",
  partial: "部分完成",
  failed: "失败",
};

const STATUS_STYLES: Record<string, string> = {
  none: "bg-slate-700/60 text-slate-400",
  generating: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  ready: "bg-pitch-500/20 text-pitch-300 ring-pitch-400/30",
  partial: "bg-orange-500/15 text-orange-300",
  failed: "bg-red-500/15 text-red-300",
};

export function MatchCard({ match }: { match: Match }) {
  const kickoff = formatKickoff(match.kickoff_at);
  const statusKey = match.deliberation_status || "none";
  const statusStyle = STATUS_STYLES[statusKey] || STATUS_STYLES.none;

  return (
    <Link
      href={`/match/${match.id}`}
      className="group relative block overflow-hidden rounded-2xl border border-pitch-700/70 bg-gradient-to-b from-pitch-800/90 to-pitch-900 p-5 shadow-lg shadow-black/10 transition duration-300 hover:-translate-y-0.5 hover:border-pitch-500/50 hover:shadow-xl hover:shadow-pitch-500/5"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-pitch-400/30 to-transparent opacity-0 transition group-hover:opacity-100" />

      <div className="mb-4 flex items-start justify-between gap-2">
        <div className="flex flex-wrap gap-2">
          {match.is_hot && (
            <span className="rounded-full bg-gold-500/15 px-2.5 py-0.5 text-xs font-medium text-gold-400 ring-1 ring-gold-500/25">
              热门
            </span>
          )}
          <span className="rounded-full bg-pitch-700/50 px-2.5 py-0.5 text-xs text-slate-400">
            {stageLabel(match.stage)}
            {match.group_code ? ` · ${match.group_code}组` : ""}
          </span>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ${statusStyle}`}
        >
          {STATUS_LABELS[statusKey] || statusKey}
        </span>
      </div>

      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1 text-center">
          <span className="text-3xl">{match.home_flag || "🏳️"}</span>
          <p className="mt-2 truncate text-sm font-semibold text-slate-100 sm:text-base">
            {match.home_team}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-center">
          <span className="rounded-lg bg-pitch-950/80 px-3 py-1 text-lg font-bold text-slate-500">
            VS
          </span>
        </div>

        <div className="min-w-0 flex-1 text-center">
          <span className="text-3xl">{match.away_flag || "🏳️"}</span>
          <p className="mt-2 truncate text-sm font-semibold text-slate-100 sm:text-base">
            {match.away_team}
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-pitch-700/60 pt-3 text-xs text-slate-500">
        <span>{kickoff} 北京时间</span>
        <span className="text-pitch-400 opacity-0 transition group-hover:opacity-100">
          查看分析 →
        </span>
      </div>
    </Link>
  );
}
