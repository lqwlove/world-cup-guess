import type { ConsensusData } from "./types";

const PICK_LABELS: Record<string, string> = {
  home: "主胜",
  draw: "平局",
  away: "客胜",
};

export interface AnalysisResult {
  pick: string;
  label: string;
  pct: number;
  score?: string | null;
  probs: Record<string, number>;
}

function normalizeProbsFromEdge(
  edges: ConsensusData["market_edge"],
): Record<string, number> {
  const raw: Record<string, number> = {};
  for (const row of edges) {
    if (row.outcome === "home" || row.outcome === "draw" || row.outcome === "away") {
      raw[row.outcome] = row.consensus_p;
    }
  }
  const total = Object.values(raw).reduce((a, b) => a + b, 0) || 1;
  const rounded: Record<string, number> = {};
  for (const [k, v] of Object.entries(raw)) {
    rounded[k] = Math.round((v / total) * 100);
  }
  const diff = 100 - Object.values(rounded).reduce((a, b) => a + b, 0);
  if (diff && Object.keys(rounded).length) {
    const top = Object.entries(rounded).sort((a, b) => b[1] - a[1])[0][0];
    rounded[top] += diff;
  }
  return rounded;
}

function topScore(data: ConsensusData): string | null {
  const scores = data.plays?.score_top3;
  if (!scores?.length) return null;
  return [...scores].sort((a, b) => b.confidence - a.confidence)[0].score;
}

export function extractAnalysisResult(data: ConsensusData): AnalysisResult | null {
  const prediction = (data as ConsensusData & { prediction?: AnalysisResult & { probs: Record<string, number> } })
    .prediction;
  if (prediction?.pick && prediction.probs) {
    const pct = prediction.probs[prediction.pick] ?? prediction.pct;
    return {
      pick: prediction.pick,
      label: PICK_LABELS[prediction.pick] || prediction.pick,
      pct: pct ?? 0,
      score: prediction.score ?? topScore(data),
      probs: prediction.probs,
    };
  }

  let probs = normalizeProbsFromEdge(data.market_edge || []);
  if (!Object.keys(probs).length) {
    const pick = data.plays?.["1x2"]?.pick;
    if (!pick || !PICK_LABELS[pick]) return null;
    const conf = data.plays["1x2"].confidence || 0.5;
    const rest = Math.max(0.1, 1 - conf);
    probs = {
      home: pick === "home" ? Math.round(conf * 100) : Math.round((rest / 2) * 100),
      draw: pick === "draw" ? Math.round(conf * 100) : Math.round((rest / 2) * 100),
      away: pick === "away" ? Math.round(conf * 100) : Math.round((rest / 2) * 100),
    };
  }

  const pick = Object.entries(probs).sort((a, b) => b[1] - a[1])[0][0];
  return {
    pick,
    label: PICK_LABELS[pick] || pick,
    pct: probs[pick],
    score: topScore(data),
    probs,
  };
}

export function formatAnalysisResultSummary(
  label: string | null | undefined,
  score?: string | null,
): string | null {
  if (!label) return null;
  return score ? `${label} · 参考比分 ${score}` : label;
}
