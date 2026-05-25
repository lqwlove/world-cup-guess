export interface Match {
  id: string;
  home_team: string;
  away_team: string;
  home_flag?: string;
  away_flag?: string;
  kickoff_at: string;
  stage: string;
  group_code?: string;
  status: string;
  is_hot: boolean;
  deliberation_status: string;
  data_version?: string;
  latest_discussion_id?: string | null;
  deliberation_error?: string | null;
}

export interface MatchFact {
  fact_type: string;
  payload: Record<string, unknown>;
  evidence_id: string;
  source: string;
  updated_at: string;
}

export interface DiscussionMessage {
  seq: number;
  role: string;
  msg_type: string;
  content: string;
  refs: string[];
  evidence_ids: string[];
  phase: string;
  created_at?: string;
}

export interface Discussion {
  id: string;
  match_id: string;
  status: string;
  phase: string;
  round: number;
  error_reason?: string;
}

export interface ConsensusArtifact {
  match_id: string;
  discussion_id: string;
  schema_version: string;
  strength: string;
  artifact: ConsensusData;
  created_at: string;
}

export interface ConsensusData {
  match_id: string;
  status: string;
  generated_at: string;
  consensus_strength: string;
  plays: {
    "1x2": {
      pick: string;
      confidence: number;
      confidence_band: [number, number];
      reasons: string[];
      dissent?: string | null;
    };
    score_top3: { score: string; confidence: number }[];
    handicap: {
      line: string;
      pick: string;
      confidence: number;
      abstain: boolean;
    };
  };
  market_edge: {
    outcome: string;
    consensus_p: number;
    market_p: number;
    edge: number;
  }[];
  minority_opinions: { role: string; summary: string }[];
  unresolved: string[];
  skeptic_ack: string;
}

export interface MarketData {
  available: boolean;
  match_id?: string;
  platform?: string;
  probabilities?: Record<string, number>;
  captured_at?: string;
  mapping?: {
    review_status: string;
    event_slug: string;
  };
  message?: string;
}
