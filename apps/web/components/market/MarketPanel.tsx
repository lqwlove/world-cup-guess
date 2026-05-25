import { formatDateTime } from "@/lib/formatDateTime";
import type { MarketData } from "@/lib/types";

const OUTCOME_LABELS: Record<string, string> = {
  home: "主胜",
  draw: "平局",
  away: "客胜",
};

export function MarketPanel({ market }: { market: MarketData }) {
  if (!market.available) {
    return (
      <div className="rounded-lg border border-pitch-700 p-4 text-slate-400">
        {market.message || "暂无预测市场映射"}
        <p className="mt-2 text-xs">Robinhood 预测市场：即将支持</p>
      </div>
    );
  }

  const probs = market.probabilities || {};
  const review = market.mapping?.review_status;

  return (
    <div>
      {review && review !== "approved" && (
        <div className="mb-3 rounded bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          映射审核状态: {review} — 请谨慎参考 Edge
        </div>
      )}
      <p className="mb-2 text-sm text-slate-400">
        {market.platform} · {market.mapping?.event_slug}
      </p>
      <div className="grid grid-cols-3 gap-3">
        {Object.entries(probs).map(([k, v]) => (
          <div key={k} className="rounded-lg border border-pitch-700 p-3 text-center">
            <p className="text-xs text-slate-400">{OUTCOME_LABELS[k] || k}</p>
            <p className="text-xl font-bold text-pitch-400">{(v * 100).toFixed(1)}%</p>
          </div>
        ))}
      </div>
      {market.captured_at && (
        <p className="mt-2 text-xs text-slate-500">
          更新于 {formatDateTime(market.captured_at)} 北京时间
        </p>
      )}
    </div>
  );
}
