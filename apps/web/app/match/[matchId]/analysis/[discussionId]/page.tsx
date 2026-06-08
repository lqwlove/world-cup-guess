import { notFound } from "next/navigation";
import { MatchHeader } from "@/components/match/MatchHeader";
import { WarRoomPanel } from "@/components/war-room/WarRoomPanel";
import {
  getDiscussion,
  getDiscussionConsensus,
  getMarket,
  getMatch,
} from "@/lib/api";

export default async function AnalysisDetailPage({
  params,
}: {
  params: Promise<{ matchId: string; discussionId: string }>;
}) {
  const { matchId, discussionId } = await params;

  let match;
  let discussion;
  try {
    [match, discussion] = await Promise.all([
      getMatch(matchId),
      getDiscussion(discussionId),
    ]);
  } catch {
    notFound();
  }

  if (discussion.match_id !== matchId) {
    notFound();
  }

  const [market, consensus] = await Promise.all([
    getMarket(matchId).catch(() => ({ available: false })),
    getDiscussionConsensus(discussionId).catch(() => null),
  ]);

  return (
    <div className="space-y-6">
      <MatchHeader
        match={match}
        backHref={`/match/${matchId}`}
        backLabel="返回分析列表"
      />
      <WarRoomPanel
        matchId={matchId}
        discussionId={discussionId}
        initialDiscussion={discussion}
        initialConsensus={consensus}
        initialMarket={market}
      />
    </div>
  );
}
