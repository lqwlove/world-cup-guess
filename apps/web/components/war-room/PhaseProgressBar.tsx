const PHASES = ["Analysis", "FollowUp", "Summary"];

const PHASE_LABELS: Record<string, string> = {
  Analysis: "分析中",
  FollowUp: "会后追问",
  Summary: "总结",
  Opening: "开场",
  CrossExam: "交叉盘问",
  DeepDive: "深度讨论",
  PlaybookSplit: "玩法分拆",
  FinalVote: "表决",
  Consensus: "共识",
};

export function PhaseProgressBar({ phase, round }: { phase: string; round: number }) {
  const idx = PHASES.indexOf(phase);
  const activeIdx = idx >= 0 ? idx : 0;

  return (
    <div className="mb-4 rounded-lg border border-pitch-700 bg-pitch-800 p-3">
      <div className="mb-2 flex justify-between text-xs text-slate-400">
        <span>AI 战术室 · 调度工作流</span>
        <span>第 {round} 轮</span>
      </div>
      <div className="flex gap-1">
        {PHASES.map((p, i) => (
          <div
            key={p}
            className={`h-1.5 flex-1 rounded-full ${
              i <= activeIdx ? "bg-pitch-400" : "bg-pitch-700"
            }`}
            title={PHASE_LABELS[p]}
          />
        ))}
      </div>
      <p className="mt-2 text-sm font-medium text-gold-400">
        {PHASE_LABELS[phase] || phase}
      </p>
    </div>
  );
}
