import { Suspense } from "react";
import { ScheduleFilters } from "@/components/schedule/ScheduleFilters";
import { MatchCard } from "@/components/schedule/MatchCard";
import { getMatches } from "@/lib/api";

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

  return (
    <div>
      <h1 className="mb-2 text-2xl font-bold">赛程</h1>
      <p className="mb-6 text-sm text-slate-400">
        以赛程为入口，查看 AI 战术室合议结论与完整讨论回放
      </p>
      <Suspense fallback={<div className="h-10" />}>
        <ScheduleFilters />
      </Suspense>
      <div className="mt-6 grid gap-4">
        {matches.length === 0 ? (
          <p className="text-slate-400">
            暂无赛程数据，请确认 API 服务已启动。
          </p>
        ) : (
          matches.map((m) => <MatchCard key={m.id} match={m} />)
        )}
      </div>
    </div>
  );
}
