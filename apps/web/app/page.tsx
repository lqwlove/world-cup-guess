import { Suspense } from "react";
import { ScheduleFilters } from "@/components/schedule/ScheduleFilters";
import { MatchCard } from "@/components/schedule/MatchCard";
import { getMatches } from "@/lib/api";
import { parseUtc } from "@/lib/formatDateTime";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string; stage?: string; group?: string }>;
}) {
  const params = await searchParams;
  let matches: Awaited<ReturnType<typeof getMatches>> = [];
  try {
    matches = await getMatches({
      date: params.date,
      stage: params.stage,
      group: params.group,
    });
  } catch {
    matches = [];
  }

  matches = [...matches].sort(
    (a, b) =>
      parseUtc(a.kickoff_at).getTime() - parseUtc(b.kickoff_at).getTime(),
  );

  return (
    <div>
      <div className="relative mb-8 overflow-hidden rounded-2xl border border-pitch-700/60 bg-gradient-to-br from-pitch-800/80 via-pitch-900 to-pitch-950 px-6 py-8">
        <div className="pointer-events-none absolute -right-16 top-0 h-40 w-40 rounded-full bg-pitch-400/10 blur-3xl" />
        <h1 className="relative text-2xl font-bold tracking-tight text-white sm:text-3xl">
          2026 世界杯赛程
        </h1>
        <p className="relative mt-2 max-w-lg text-sm leading-relaxed text-slate-400">
          选择比赛进入战术室，可多次新建 AI 合议分析，查看历史讨论与专家辩论回放
        </p>
      </div>

      <Suspense fallback={<div className="h-10 animate-pulse rounded-lg bg-pitch-800" />}>
        <ScheduleFilters />
      </Suspense>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {matches.length === 0 ? (
          <div className="col-span-full rounded-2xl border border-dashed border-pitch-600 py-16 text-center text-slate-500">
            暂无赛程数据，请确认 API 服务已启动
          </div>
        ) : (
          matches.map((m) => <MatchCard key={m.id} match={m} />)
        )}
      </div>
    </div>
  );
}
