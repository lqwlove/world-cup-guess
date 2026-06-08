import Link from "next/link";
import type { ReactNode } from "react";
import type { Match } from "@/lib/types";
import { formatDateTime } from "@/lib/formatDateTime";
import { stageLabel } from "@/lib/stageLabels";

export function MatchHeader({
  match,
  backHref = "/",
  backLabel = "返回赛程",
  extra,
}: {
  match: Match;
  backHref?: string;
  backLabel?: string;
  extra?: ReactNode;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-pitch-700/80 bg-gradient-to-br from-pitch-800 via-pitch-900 to-pitch-950 p-5 shadow-lg shadow-black/20">
      <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-pitch-500/10 blur-2xl" />
      <div className="pointer-events-none absolute -bottom-10 -left-10 h-28 w-28 rounded-full bg-gold-500/5 blur-2xl" />
      <Link
        href={backHref}
        className="relative mb-4 inline-flex items-center gap-1 text-sm text-pitch-400 transition hover:text-pitch-300"
      >
        ← {backLabel}
      </Link>
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 flex-1 items-center justify-center gap-3 sm:gap-6">
          <div className="text-center">
            <span className="text-3xl sm:text-4xl">{match.home_flag || "🏳️"}</span>
            <p className="mt-2 max-w-[8rem] truncate text-sm font-semibold sm:max-w-none sm:text-base">
              {match.home_team}
            </p>
          </div>
          <div className="flex flex-col items-center px-2">
            <span className="rounded-full bg-pitch-700/80 px-3 py-1 text-xs font-medium text-slate-400">
              VS
            </span>
            <p className="mt-2 text-center text-xs text-slate-500">
              {formatDateTime(match.kickoff_at)}
            </p>
          </div>
          <div className="text-center">
            <span className="text-3xl sm:text-4xl">{match.away_flag || "🏳️"}</span>
            <p className="mt-2 max-w-[8rem] truncate text-sm font-semibold sm:max-w-none sm:text-base">
              {match.away_team}
            </p>
          </div>
        </div>
        {extra}
      </div>
      <p className="relative mt-4 text-center text-xs text-slate-500">
        {stageLabel(match.stage)}
        {match.group_code ? ` · ${match.group_code} 组` : ""}
      </p>
    </div>
  );
}
