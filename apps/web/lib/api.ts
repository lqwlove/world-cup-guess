import type {
  ConsensusArtifact,
  Discussion,
  DiscussionListItem,
  DiscussionMessage,
  MarketData,
  Match,
  MatchFact,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export async function getMatches(params?: {
  date?: string;
  stage?: string;
  group?: string;
}): Promise<Match[]> {
  const q = new URLSearchParams();
  if (params?.date) q.set("date", params.date);
  if (params?.stage) q.set("stage", params.stage);
  if (params?.group) q.set("group", params.group);
  const qs = q.toString();
  return fetchJson(`/api/matches${qs ? `?${qs}` : ""}`);
}

export async function getMatch(id: string): Promise<Match> {
  return fetchJson(`/api/matches/${id}`);
}

export async function getFacts(
  id: string,
): Promise<{ match_id: string; data_version: string; facts: MatchFact[] }> {
  return fetchJson(`/api/matches/${id}/facts`);
}

export async function getMarket(id: string): Promise<MarketData> {
  return fetchJson(`/api/matches/${id}/market`);
}

export async function getConsensus(
  id: string,
): Promise<ConsensusArtifact | null> {
  try {
    return await fetchJson(`/api/matches/${id}/consensus`);
  } catch {
    return null;
  }
}

export async function getDiscussionConsensus(
  discussionId: string,
): Promise<ConsensusArtifact | null> {
  try {
    return await fetchJson(`/api/discussions/${discussionId}/consensus`);
  } catch {
    return null;
  }
}

export async function listDiscussions(
  matchId: string,
): Promise<DiscussionListItem[]> {
  return fetchJson(`/api/matches/${matchId}/discussions`);
}

export async function startDiscussion(
  matchId: string,
  forceRefresh = false,
  autoStart = true,
): Promise<Discussion> {
  return fetchJson(`/api/matches/${matchId}/discussions`, {
    method: "POST",
    body: JSON.stringify({ force_refresh: forceRefresh, auto_start: autoStart }),
  });
}

export async function createDiscussionDraft(
  matchId: string,
): Promise<Discussion> {
  return startDiscussion(matchId, true, false);
}

export async function runDiscussionAnalysis(
  discussionId: string,
): Promise<Discussion> {
  return fetchJson(`/api/discussions/${discussionId}/start`, { method: "POST" });
}

export async function stopDiscussionAnalysis(
  discussionId: string,
): Promise<Discussion> {
  return fetchJson(`/api/discussions/${discussionId}/stop`, { method: "POST" });
}

export async function getDiscussion(id: string): Promise<Discussion> {
  return fetchJson(`/api/discussions/${id}`);
}

export async function getMessages(
  discussionId: string,
  fromSeq = 0,
): Promise<DiscussionMessage[]> {
  return fetchJson(
    `/api/discussions/${discussionId}/messages?from_seq=${fromSeq}`,
  );
}

export async function runDiscussionSync(
  discussionId: string,
): Promise<Discussion> {
  return fetchJson(`/api/discussions/${discussionId}/run-sync`, {
    method: "POST",
  });
}

export async function getLatestDiscussion(matchId: string): Promise<Discussion> {
  return fetchJson(`/api/matches/${matchId}/discussions/latest`);
}

export async function retryDiscussion(discussionId: string): Promise<Discussion> {
  return fetchJson(`/api/discussions/${discussionId}/retry`, { method: "POST" });
}

export async function resumeDiscussion(
  discussionId: string,
  reply: string,
): Promise<Discussion> {
  return fetchJson(`/api/discussions/${discussionId}/resume`, {
    method: "POST",
    body: JSON.stringify({ reply }),
  });
}

export async function followupChat(
  discussionId: string,
  question: string,
): Promise<Discussion> {
  return fetchJson(`/api/discussions/${discussionId}/chat`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

export function streamDiscussion(
  discussionId: string,
  onEvent: (data: unknown) => void,
  onError?: (e: Event) => void,
): EventSource {
  const es = new EventSource(
    `${API_URL}/api/discussions/${discussionId}/stream`,
  );
  const handle = (e: MessageEvent) => {
    try {
      onEvent(JSON.parse(e.data));
    } catch {
      onEvent(e.data);
    }
  };
  for (const name of ["message", "status", "consensus", "error", "connected", "ping"]) {
    es.addEventListener(name, handle);
  }
  es.onerror = (e) => onError?.(e);
  return es;
}

export async function submitFeedback(
  matchId: string,
  sessionId: string,
  vote: "up" | "down",
): Promise<void> {
  await fetchJson("/api/feedback", {
    method: "POST",
    body: JSON.stringify({ match_id: matchId, session_id: sessionId, vote }),
  });
}

export function getSessionId(): string {
  if (typeof window === "undefined") return "server";
  let id = localStorage.getItem("wc_session_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("wc_session_id", id);
  }
  return id;
}
