import { formatDateTime } from "@/lib/formatDateTime";
import type { MarketData } from "@/lib/types";

const OUTCOME_LABELS: Record<string, string> = {
  home: "主胜",
  draw: "平局",
  away: "客胜",
};

export function MarketSnapshotStrip({ market }: { market: MarketData }) {
  if (!market.available) {
    return (
      <p className="mb-4 rounded-lg border border-pitch-700/80 bg-pitch-800/40 px-3 py-2 text-xs text-slate-500">
        预测市场：未配置映射，合议将仅依据基本面与技术面（可在 seeds/market_mappings.json 配置
        Polymarket）。
      </p>
    );
  }

  const probs = market.probabilities || {};

  return (
    <div className="mb-4 rounded-lg border border-pitch-700 bg-pitch-800/50 px-4 py-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-slate-300">
          预测市场 · {market.platform || "polymarket"}
          {market.mapping?.event_slug ? ` · ${market.mapping.event_slug}` : ""}
        </p>
        {market.captured_at && (
          <p className="text-xs text-slate-500">
            快照 {formatDateTime(market.captured_at)} 北京时间
          </p>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2">
        {Object.entries(probs).map(([k, v]) => (
          <div key={k} className="rounded-md border border-pitch-700/80 px-2 py-1.5 text-center">
            <p className="text-[10px] text-slate-500">{OUTCOME_LABELS[k] || k}</p>
            <p className="text-sm font-semibold text-pitch-400">{(v * 100).toFixed(1)}%</p>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-slate-500">
        市场官等角色在合议中会引用上述隐含概率，共识证书中的 Edge 表亦据此计算。
      </p>
    </div>
  );
}
