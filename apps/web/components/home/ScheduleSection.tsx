import { Suspense } from "react";
import { ScheduleFilters } from "@/components/schedule/ScheduleFilters";
import { MatchCard } from "@/components/schedule/MatchCard";
import { getMatches } from "@/lib/api";
import { parseUtc } from "@/lib/formatDateTime";

export async function ScheduleSection({
  searchParams,
}: {
  searchParams: { date?: string; stage?: string; group?: string };
}) {
  let matches: Awaited<ReturnType<typeof getMatches>> = [];
  try {
    matches = await getMatches({
      date: searchParams.date,
      stage: searchParams.stage,
      group: searchParams.group,
    });
  } catch {
    matches = [];
  }

  matches = [...matches].sort(
    (a, b) =>
      parseUtc(a.kickoff_at).getTime() - parseUtc(b.kickoff_at).getTime(),
  );

  return (
    <section id="schedule" className="scroll-mt-20 border-t border-pitch-800/80 pt-12 sm:pt-14">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white sm:text-3xl">
            2026 世界杯赛程
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            选择比赛进入战术室，可多次新建 AI 合议分析
          </p>
        </div>
      </div>

      <Suspense
        fallback={
          <div className="h-10 animate-pulse rounded-lg bg-pitch-800" />
        }
      >
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
    </section>
  );
}
