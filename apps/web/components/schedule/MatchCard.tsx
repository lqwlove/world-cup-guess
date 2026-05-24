import Link from "next/link";
import type { Match } from "@/lib/types";

const STATUS_LABELS: Record<string, string> = {
  none: "未分析",
  generating: "合议生成中",
  ready: "已有共识",
  partial: "部分共识",
  failed: "生成失败",
};

const STATUS_COLORS: Record<string, string> = {
  none: "bg-slate-600",
  generating: "bg-amber-600 animate-pulse",
  ready: "bg-pitch-500",
  partial: "bg-orange-600",
  failed: "bg-red-600",
};

export function MatchCard({ match }: { match: Match }) {
  const kickoff = new Date(match.kickoff_at).toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <Link
      href={`/match/${match.id}`}
      className="block rounded-xl border border-pitch-700 bg-pitch-800 p-4 transition hover:border-pitch-500"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          {match.is_hot && (
            <span className="mb-1 inline-block rounded bg-gold-500/20 px-2 py-0.5 text-xs text-gold-400">
              热门
            </span>
          )}
          <p className="text-lg font-semibold">
            {match.home_flag} {match.home_team}{" "}
            <span className="text-slate-400">vs</span> {match.away_flag}{" "}
            {match.away_team}
          </p>
          <p className="mt-1 text-sm text-slate-400">
            {kickoff} · {match.stage}
            {match.group_code ? ` · 小组 ${match.group_code}` : ""}
          </p>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-1 text-xs text-white ${STATUS_COLORS[match.deliberation_status] || STATUS_COLORS.none}`}
        >
          {STATUS_LABELS[match.deliberation_status] || match.deliberation_status}
        </span>
      </div>
    </Link>
  );
}
