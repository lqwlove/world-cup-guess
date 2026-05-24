import type { MatchFact } from "@/lib/types";

export function MatchDataPanel({
  facts,
  dataVersion,
}: {
  facts: MatchFact[];
  dataVersion: string;
}) {
  const byType = facts.reduce<Record<string, MatchFact[]>>((acc, f) => {
    if (!acc[f.fact_type]) acc[f.fact_type] = [];
    acc[f.fact_type].push(f);
    return acc;
  }, {});

  return (
    <div>
      <p className="mb-4 text-xs text-slate-500">数据版本: {dataVersion}</p>
      {Object.entries(byType).map(([type, items]) => (
        <section key={type} className="mb-6">
          <h3 className="mb-2 text-sm font-medium capitalize text-slate-300">
            {type.replace(/_/g, " ")}
          </h3>
          <ul className="space-y-2">
            {items.map((f) => (
              <li
                key={f.evidence_id}
                className="rounded-lg border border-pitch-700 bg-pitch-800/50 p-3 text-sm"
              >
                <div className="mb-1 flex gap-2 text-xs">
                  <span className="rounded bg-pitch-700 px-1.5 text-pitch-400">
                    {f.evidence_id}
                  </span>
                  <span className="text-slate-500">{f.source}</span>
                </div>
                <pre className="whitespace-pre-wrap font-sans text-slate-200">
                  {JSON.stringify(f.payload, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {facts.length === 0 && (
        <p className="text-slate-400">暂无结构化事实数据</p>
      )}
    </div>
  );
}
