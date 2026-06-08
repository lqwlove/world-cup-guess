"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getDiscussion,
  getDiscussionConsensus,
  getMessages,
  followupChat,
  resumeDiscussion,
  retryDiscussion,
  streamDiscussion,
  submitFeedback,
  getSessionId,
} from "@/lib/api";
import type {
  ConsensusArtifact,
  Discussion,
  DiscussionMessage,
  MarketData,
} from "@/lib/types";
import { MarketSnapshotStrip } from "./MarketSnapshotStrip";
import { PhaseProgressBar } from "./PhaseProgressBar";
import { ChatRoom, type LiveToolCall } from "./ChatRoom";
import { PlaysRecommendation } from "./ConsensusCertificate";
import { MarketEdgeTable } from "./MarketEdgeTable";
import { MinorityOpinions } from "./MinorityOpinions";

const TERMINAL = new Set(["completed", "partial", "failed"]);
const ACTIVE = new Set(["running", "pending", "awaiting_user"]);

export function WarRoomPanel({
  matchId,
  discussionId,
  initialDiscussion,
  initialConsensus,
  initialMarket,
}: {
  matchId: string;
  discussionId: string;
  initialDiscussion: Discussion;
  initialConsensus: ConsensusArtifact | null;
  initialMarket: MarketData;
}) {
  const [consensus, setConsensus] = useState(initialConsensus);
  const [discussion, setDiscussion] = useState<Discussion>(initialDiscussion);
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [isLive, setIsLive] = useState(false);
  const [error, setError] = useState<string | null>(
    initialDiscussion.error_reason || null,
  );
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [userInput, setUserInput] = useState("");
  const [sendingUser, setSendingUser] = useState(false);
  const [analyzingRole, setAnalyzingRole] = useState<string | null>(null);
  const [liveToolCalls, setLiveToolCalls] = useState<LiveToolCall[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const loadConsensus = useCallback(async () => {
    const c = await getDiscussionConsensus(discussionId);
    setConsensus(c);
  }, [discussionId]);

  const loadMessages = useCallback(async (fromSeq = 0) => {
    const msgs = await getMessages(discussionId, fromSeq);
    if (fromSeq > 0) {
      setMessages((prev) => {
        const seen = new Set(prev.map((p) => p.seq));
        return [...prev, ...msgs.filter((m) => !seen.has(m.seq))];
      });
    } else {
      setMessages(msgs);
    }
  }, [discussionId]);

  const clearAgentActivity = useCallback(() => {
    setAnalyzingRole(null);
    setLiveToolCalls([]);
  }, []);

  const stopLive = useCallback(() => {
    setIsLive(false);
    clearAgentActivity();
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }, [clearAgentActivity]);

  const watchDiscussion = useCallback(
    async (disc: Discussion) => {
      setDiscussion(disc);
      if (TERMINAL.has(disc.status) || disc.status === "awaiting_user") {
        stopLive();
        await loadMessages();
        if (disc.status !== "failed" && disc.status !== "awaiting_user") {
          await loadConsensus();
        }
        return;
      }

      setIsLive(true);
      await loadMessages();

      const refresh = async () => {
        try {
          await loadMessages();
          const d = await getDiscussion(discussionId);
          setDiscussion(d);
          if (TERMINAL.has(d.status) || d.status === "awaiting_user") {
            stopLive();
            if (d.status === "failed") {
              setError(d.error_reason || "合议生成失败");
            } else if (d.status !== "awaiting_user") {
              await loadConsensus();
            }
          }
        } catch {
          /* ignore poll errors */
        }
      };

      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(refresh, 2000);

      if (esRef.current) esRef.current.close();
      esRef.current = streamDiscussion(discussionId, async (evt) => {
        const e = evt as {
          type?: string;
          msg_type?: string;
          message?: string;
          role?: string;
          tool?: string;
          args?: Record<string, unknown>;
          result_preview?: string;
          index?: number;
        };
        if (e.type === "agent_analyzing" && e.role) {
          setAnalyzingRole(e.role);
          setLiveToolCalls([]);
        }
        if (e.type === "tool_call" && e.tool) {
          setAnalyzingRole((prev) => e.role || prev);
          setLiveToolCalls((prev) => [
            ...prev,
            {
              tool: e.tool!,
              args: e.args,
              result_preview: e.result_preview,
              index: e.index,
            },
          ]);
        }
        if (e.type === "message" || e.type === "status") {
          await loadMessages();
          const d = await getDiscussion(discussionId);
          setDiscussion(d);
          if (e.type === "message" && e.msg_type === "TOOL_CALL") {
            setLiveToolCalls([]);
          } else if (e.type === "message" && e.msg_type) {
            clearAgentActivity();
          }
          if (TERMINAL.has(d.status) || d.status === "awaiting_user") {
            stopLive();
            if (d.status !== "failed" && d.status !== "awaiting_user") {
              await loadConsensus();
            }
          }
        }
        if (e.type === "consensus") {
          await loadConsensus();
        }
        if (e.type === "error") {
          setError(e.message || "合议出错");
          stopLive();
        }
      });
    },
    [clearAgentActivity, discussionId, loadConsensus, loadMessages, stopLive],
  );

  const handleRetry = async () => {
    setLoading(true);
    setError(null);
    try {
      const disc = await retryDiscussion(discussionId);
      setConsensus(null);
      await watchDiscussion(disc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重试失败");
      stopLive();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const boot = async () => {
      await loadMessages();
      if (!cancelled && ACTIVE.has(initialDiscussion.status)) {
        await watchDiscussion(initialDiscussion);
      }
    };
    void boot();
    return () => {
      cancelled = true;
      stopLive();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- boot once per discussionId
  }, [discussionId]);

  const artifact = consensus?.artifact;
  const isProcessing =
    discussion.status === "running" || discussion.status === "pending";
  const canUserInput =
    !isProcessing &&
    (discussion.status === "awaiting_user" || discussion.status === "completed");
  const inputPlaceholder = isProcessing
    ? "专家分析中，请稍候…"
    : discussion.status === "awaiting_user"
      ? "调度官在等待你的回答…"
      : "分析完成后可继续追问各专家…";

  const handleUserSend = async () => {
    const text = userInput.trim();
    if (!text || sendingUser) return;
    setSendingUser(true);
    setError(null);
    try {
      const updated =
        discussion.status === "awaiting_user"
          ? await resumeDiscussion(discussionId, text)
          : await followupChat(discussionId, text);
      setUserInput("");
      setDiscussion(updated);
      await loadMessages();
      await watchDiscussion({ ...updated, status: "running" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送失败");
    } finally {
      setSendingUser(false);
    }
  };

  const showChat =
    isLive ||
    messages.length > 0 ||
    ACTIVE.has(discussion.status);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-bold">AI 战术室合议</h2>
        <span className="text-xs text-slate-500">
          调度官编排各专家；分析中可向你提问，完成后可继续追问
        </span>
      </div>

      <MarketSnapshotStrip market={initialMarket} />

      <PhaseProgressBar phase={discussion.phase} round={discussion.round} />

      {showChat && (
        <div className="mb-4">
          <ChatRoom
            messages={messages}
            isLive={isLive}
            analyzingRole={analyzingRole}
            liveToolCalls={liveToolCalls}
            input={
              canUserInput || isProcessing ? (
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={userInput}
                    onChange={(e) => setUserInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && canUserInput) void handleUserSend();
                    }}
                    placeholder={inputPlaceholder}
                    disabled={!canUserInput || sendingUser}
                    className="min-w-0 flex-1 rounded-lg border border-pitch-600 bg-pitch-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-pitch-400 focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
                  />
                  <button
                    type="button"
                    onClick={() => void handleUserSend()}
                    disabled={!canUserInput || sendingUser || !userInput.trim()}
                    className="shrink-0 rounded-lg bg-pitch-500 px-4 py-2 text-sm text-white hover:bg-pitch-400 disabled:opacity-50"
                  >
                    {sendingUser ? "提交中…" : isProcessing ? "分析中…" : "发送"}
                  </button>
                </div>
              ) : undefined
            }
          />
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg border border-red-800/60 bg-red-950/30 px-4 py-3 text-sm text-red-300">
          <p className="font-medium">合议未成功</p>
          <p className="mt-1 text-red-200/80">{error}</p>
          <button
            type="button"
            onClick={() => void handleRetry()}
            disabled={loading}
            className="mt-3 rounded-lg bg-red-600 px-4 py-1.5 text-sm text-white hover:bg-red-500 disabled:opacity-50"
          >
            {loading ? "重新生成中…" : "重新生成本次分析"}
          </button>
        </div>
      )}

      {discussion.status === "failed" && !error && (
        <button
          type="button"
          onClick={() => void handleRetry()}
          disabled={loading}
          className="mb-4 text-sm text-pitch-400 underline hover:text-pitch-300"
        >
          {loading ? "重新生成中…" : "重新生成本次分析"}
        </button>
      )}

      {artifact && (
        <>
          <PlaysRecommendation data={artifact} />
          <MarketEdgeTable edges={artifact.market_edge} />
          <MinorityOpinions opinions={artifact.minority_opinions} />
        </>
      )}

      {artifact && (
        <div className="mt-6 flex gap-2">
          <button
            type="button"
            disabled={feedbackSent}
            onClick={async () => {
              await submitFeedback(matchId, getSessionId(), "up");
              setFeedbackSent(true);
            }}
            className="rounded border border-pitch-600 px-3 py-1 text-sm hover:bg-pitch-800"
          >
            👍 有帮助
          </button>
          <button
            type="button"
            disabled={feedbackSent}
            onClick={async () => {
              await submitFeedback(matchId, getSessionId(), "down");
              setFeedbackSent(true);
            }}
            className="rounded border border-pitch-600 px-3 py-1 text-sm hover:bg-pitch-800"
          >
            👎
          </button>
        </div>
      )}
    </div>
  );
}
