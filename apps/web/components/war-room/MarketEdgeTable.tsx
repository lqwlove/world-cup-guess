import type { ConsensusData } from "@/lib/types";

const OUTCOME_LABELS: Record<string, string> = {
  home: "主胜",
  draw: "平局",
  away: "客胜",
};

export function MarketEdgeTable({ edges }: { edges: ConsensusData["market_edge"] }) {
  if (!edges?.length) return null;

  return (
    <div className="mt-4">
      <h4 className="mb-2 text-sm font-medium text-slate-300">
        相对市场预期偏差（Edge）
      </h4>
      <p className="mb-2 text-xs text-slate-500">
        Edge = 共识概率 − 市场隐含概率；数值越大表示相对市场预期偏差越大
      </p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-pitch-700 text-left text-slate-400">
            <th className="py-2">结果</th>
            <th>共识</th>
            <th>市场</th>
            <th>Edge</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((row) => (
            <tr key={row.outcome} className="border-b border-pitch-800">
              <td className="py-2">{OUTCOME_LABELS[row.outcome] || row.outcome}</td>
              <td>{(row.consensus_p * 100).toFixed(1)}%</td>
              <td>{(row.market_p * 100).toFixed(1)}%</td>
              <td
                className={
                  row.edge > 0.03 ? "text-pitch-400 font-medium" : "text-slate-300"
                }
              >
                {row.edge > 0 ? "+" : ""}
                {(row.edge * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
