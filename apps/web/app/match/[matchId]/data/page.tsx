import { notFound } from "next/navigation";
import { MatchDataPanel } from "@/components/match-data/MatchDataPanel";
import { MatchHeader } from "@/components/match/MatchHeader";
import { getFacts, getMatch } from "@/lib/api";

export default async function MatchDataPage({
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

  const factsBundle = await getFacts(matchId).catch(() => ({
    match_id: matchId,
    data_version: "v1",
    facts: [],
  }));

  return (
    <div className="space-y-6">
      <MatchHeader
        match={match}
        backHref={`/match/${matchId}`}
        backLabel="返回分析列表"
      />
      <MatchDataPanel
        facts={factsBundle.facts}
        dataVersion={factsBundle.data_version}
      />
    </div>
  );
}
