import { extractAnalysisResult } from "@/lib/analysisResult";
import type { ConsensusData } from "@/lib/types";

export function AnalysisResultCard({ data }: { data: ConsensusData }) {
  const result = extractAnalysisResult(data);
  if (!result) return null;

  return (
    <div className="mt-4 rounded-xl border border-pitch-600/80 bg-gradient-to-br from-pitch-800/90 to-pitch-900/90 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        合议结论
      </p>
      <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-2xl font-bold text-pitch-300">
          {result.label}
        </span>
        {result.score && (
          <span className="text-sm text-slate-400">
            参考比分 <span className="font-semibold text-slate-200">{result.score}</span>
          </span>
        )}
      </div>
    </div>
  );
}

export function AnalysisResultInline({
  label,
  score,
}: {
  label: string;
  score?: string | null;
}) {
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-sm">
      <span className="font-semibold text-pitch-300">{label}</span>
      {score && (
        <span className="text-slate-500">· 参考比分 {score}</span>
      )}
    </span>
  );
}
