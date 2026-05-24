import type { ConsensusData } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  skeptic: "风控官",
  data: "数据官",
  market: "市场官",
};

export function MinorityOpinions({
  opinions,
}: {
  opinions: ConsensusData["minority_opinions"];
}) {
  if (!opinions?.length) return null;

  return (
    <div className="mt-4 rounded-lg border border-orange-500/30 bg-orange-500/5 p-3">
      <h4 className="mb-2 text-sm font-medium text-orange-300">少数意见</h4>
      <ul className="space-y-2 text-sm">
        {opinions.map((o, i) => (
          <li key={i}>
            <span className="text-orange-400">{ROLE_LABELS[o.role] || o.role}: </span>
            {o.summary}
          </li>
        ))}
      </ul>
    </div>
  );
}
