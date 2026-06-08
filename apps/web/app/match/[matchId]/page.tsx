import Link from "next/link";
import { notFound } from "next/navigation";
import { AnalysisListPanel } from "@/components/match/AnalysisListPanel";
import { MatchHeader } from "@/components/match/MatchHeader";
import { getMatch, listDiscussions } from "@/lib/api";

export default async function MatchAnalysisListPage({
  params,
}: {
  params: Promise<{ matchId: string }>;
}) {
  const { matchId } = await params;

  let match;
  try {
    match = await getMatch(matchId);
  } catch {
    notFound();
  }

  const discussions = await listDiscussions(matchId).catch(() => []);

  return (
    <div className="space-y-6">
      <MatchHeader
        match={match}
        extra={
          <Link
            href={`/match/${matchId}/data`}
            className="shrink-0 rounded-lg border border-pitch-600 px-3 py-1.5 text-xs text-slate-400 transition hover:border-pitch-500 hover:text-slate-200"
          >
            数据概览
          </Link>
        }
      />
      <AnalysisListPanel matchId={matchId} initialDiscussions={discussions} />
    </div>
  );
}
