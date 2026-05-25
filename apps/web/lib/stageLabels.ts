const STAGE_LABELS: Record<string, string> = {
  group: "小组赛",
  round32: "32强",
  round16: "16强",
  quarter: "8强",
  semifinal: "半决赛",
  third_place: "三四名",
  final: "决赛",
};

export function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}
