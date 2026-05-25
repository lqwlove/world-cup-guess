import { formatDateTime } from "@/lib/formatDateTime";
import type { ConsensusData } from "@/lib/types";

const PICK_LABELS: Record<string, string> = {
  home: "主胜",
  draw: "平局",
  away: "客胜",
};

export function ConsensusCertificate({ data }: { data: ConsensusData }) {
  const ackLabel =
    data.skeptic_ack === "ACK_WITH_RESERVATION"
      ? "风控官保留意见签字"
      : data.skeptic_ack === "ACK"
        ? "风控官已签字"
        : "待签字";

  return (
    <div className="rounded-xl border border-gold-500/40 bg-gradient-to-br from-pitch-800 to-pitch-900 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-bold text-gold-400">共识证书</h3>
        <span className="rounded bg-pitch-500/30 px-2 py-0.5 text-xs">
          {data.consensus_strength === "strong"
            ? "强共识"
            : data.consensus_strength === "weak"
              ? "分裂共识"
              : "部分共识"}
        </span>
      </div>
      <p className="text-xs text-slate-400">
        {data.status} · {formatDateTime(data.generated_at)} 北京时间 · {ackLabel}
      </p>
      {data.unresolved?.length > 0 && (
        <div className="mt-2 rounded bg-orange-500/10 p-2 text-xs text-orange-300">
          未决议题: {data.unresolved.join("; ")}
        </div>
      )}
    </div>
  );
}

export function PlaysRecommendation({ data }: { data: ConsensusData }) {
  const p = data.plays;
  return (
    <div className="mt-4 grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-pitch-700 p-3">
        <h4 className="text-xs text-slate-400">胜平负</h4>
        <p className="text-lg font-bold text-pitch-400">
          {PICK_LABELS[p["1x2"].pick] || p["1x2"].pick}
        </p>
        <p className="text-sm">置信度 {(p["1x2"].confidence * 100).toFixed(0)}%</p>
        {p["1x2"].dissent && (
          <p className="mt-1 text-xs text-amber-400">{p["1x2"].dissent}</p>
        )}
      </div>
      <div className="rounded-lg border border-pitch-700 p-3">
        <h4 className="text-xs text-slate-400">比分 Top3</h4>
        <ul className="text-sm">
          {p.score_top3.map((s) => (
            <li key={s.score}>
              {s.score} · {(s.confidence * 100).toFixed(0)}%
            </li>
          ))}
        </ul>
      </div>
      <div className="rounded-lg border border-pitch-700 p-3">
        <h4 className="text-xs text-slate-400">让球胜平负</h4>
        {p.handicap.abstain ? (
          <p className="text-amber-400">不建议给出方向</p>
        ) : (
          <>
            <p className="font-bold">
              {p.handicap.line} · {PICK_LABELS[p.handicap.pick]}
            </p>
            <p className="text-sm">{(p.handicap.confidence * 100).toFixed(0)}%</p>
          </>
        )}
      </div>
    </div>
  );
}
