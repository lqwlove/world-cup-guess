import Link from "next/link";
import { notFound } from "next/navigation";
import { MatchDataPanel } from "@/components/match-data/MatchDataPanel";
import { MarketPanel } from "@/components/market/MarketPanel";
import { WarRoomPanel } from "@/components/war-room/WarRoomPanel";
import { getConsensus, getFacts, getMarket, getMatch } from "@/lib/api";

export default async function MatchPage({
  params,
  searchParams,
}: {
  params: Promise<{ matchId: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { matchId } = await params;
  const { tab = "war-room" } = await searchParams;

  let match;
  try {
    match = await getMatch(matchId);
  } catch {
    notFound();
  }

  const [factsBundle, market, consensus] = await Promise.all([
    getFacts(matchId).catch(() => ({ match_id: matchId, data_version: "v1", facts: [] })),
    getMarket(matchId).catch(() => ({ available: false })),
    getConsensus(matchId).catch(() => null),
  ]);

  const tabs = [
    { id: "war-room", label: "AI 战术室" },
    { id: "data", label: "数据概览" },
    { id: "market", label: "预测市场" },
  ];

  return (
    <div>
      <Link href="/" className="mb-4 inline-block text-sm text-pitch-400 hover:underline">
        ← 返回赛程
      </Link>
      <h1 className="text-2xl font-bold">
        {match.home_flag} {match.home_team}{" "}
        <span className="text-slate-400">vs</span> {match.away_flag} {match.away_team}
      </h1>
      <p className="mt-1 text-sm text-slate-400">
        {new Date(match.kickoff_at).toLocaleString("zh-CN")} · {match.stage}
      </p>

      <nav className="mt-6 flex gap-2 border-b border-pitch-700">
        {tabs.map((t) => (
          <Link
            key={t.id}
            href={`/match/${matchId}?tab=${t.id}`}
            className={`border-b-2 px-4 py-2 text-sm ${
              tab === t.id
                ? "border-pitch-400 text-pitch-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            {t.label}
          </Link>
        ))}
      </nav>

      <div className="mt-6">
        {tab === "war-room" && (
          <WarRoomPanel
            matchId={matchId}
            initialConsensus={consensus}
            deliberationStatus={match.deliberation_status}
          />
        )}
        {tab === "data" && (
          <MatchDataPanel facts={factsBundle.facts} dataVersion={factsBundle.data_version} />
        )}
        {tab === "market" && <MarketPanel market={market} />}
      </div>
    </div>
  );
}
