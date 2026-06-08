"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getConsensus,
  getDiscussion,
  getLatestDiscussion,
  getMessages,
  followupChat,
  resumeDiscussion,
  retryDiscussion,
  startDiscussion,
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
import { ConsensusCertificate, PlaysRecommendation } from "./ConsensusCertificate";
import { MarketEdgeTable } from "./MarketEdgeTable";
import { MinorityOpinions } from "./MinorityOpinions";
import { ReadModeToggle, type ReadMode } from "./ReadModeToggle";
import { DisagreementRadar } from "./DisagreementRadar";
import { MessageTimeline } from "./MessageTimeline";

const TERMINAL = new Set(["completed", "partial", "failed"]);

export function WarRoomPanel({
  matchId,
  initialConsensus,
  initialMarket,
  deliberationStatus,
  initialDiscussionId,
  deliberationError,
}: {
  matchId: string;
  initialConsensus: ConsensusArtifact | null;
  initialMarket: MarketData;
  deliberationStatus: string;
  initialDiscussionId?: string | null;
  deliberationError?: string | null;
}) {
  const [consensus, setConsensus] = useState(initialConsensus);
  const [discussion, setDiscussion] = useState<Discussion | null>(null);
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [readMode, setReadMode] = useState<ReadMode>("full");
  const [loading, setLoading] = useState(false);
  const [isLive, setIsLive] = useState(false);
  const [error, setError] = useState<string | null>(deliberationError || null);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [userInput, setUserInput] = useState("");
  const [sendingUser, setSendingUser] = useState(false);
  const [analyzingRole, setAnalyzingRole] = useState<string | null>(null);
  const [liveToolCalls, setLiveToolCalls] = useState<LiveToolCall[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const loadMessages = useCallback(async (discussionId: string, fromSeq = 0) => {
    const msgs = await getMessages(discussionId, fromSeq);
    if (fromSeq > 0) {
      setMessages((prev) => {
        const seen = new Set(prev.map((p) => p.seq));
        return [...prev, ...msgs.filter((m) => !seen.has(m.seq))];
      });
    } else {
      setMessages(msgs);
    }
  }, []);

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
        await loadMessages(disc.id);
        if (disc.status !== "failed" && disc.status !== "awaiting_user") {
          const c = await getConsensus(matchId);
          setConsensus(c);
        }
        return;
      }

      setIsLive(true);
      await loadMessages(disc.id);

      const refresh = async () => {
        try {
          await loadMessages(disc.id);
          const d = await getDiscussion(disc.id);
          setDiscussion(d);
          if (TERMINAL.has(d.status) || d.status === "awaiting_user") {
            stopLive();
            if (d.status === "failed") {
              setError(d.error_reason || "合议生成失败");
            } else if (d.status !== "awaiting_user") {
              const c = await getConsensus(matchId);
              setConsensus(c);
            }
          }
        } catch {
          /* ignore poll errors */
        }
      };

      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(refresh, 2000);

      if (esRef.current) esRef.current.close();
      esRef.current = streamDiscussion(disc.id, async (evt) => {
        const e = evt as {
          type?: string;
          seq?: number;
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
          await loadMessages(disc.id);
          const d = await getDiscussion(disc.id);
          setDiscussion(d);
          if (e.type === "message" && e.msg_type === "TOOL_CALL") {
            setLiveToolCalls([]);
          } else if (e.type === "message" && e.msg_type) {
            clearAgentActivity();
          }
          if (TERMINAL.has(d.status) || d.status === "awaiting_user") {
            stopLive();
            if (d.status !== "failed" && d.status !== "awaiting_user") {
              const c = await getConsensus(matchId);
              setConsensus(c);
            }
          }
        }
        if (e.type === "consensus") {
          const c = await getConsensus(matchId);
          setConsensus(c);
        }
        if (e.type === "error") {
          setError(e.message || "合议出错");
          stopLive();
        }
      });
    },
    [clearAgentActivity, loadMessages, matchId, stopLive],
  );

  const runDeliberation = useCallback(
    async (disc: Discussion) => {
      setError(null);
      setConsensus(null);
      await watchDiscussion(disc);
    },
    [watchDiscussion],
  );

  const handleStart = async (forceRefresh = false) => {
    setLoading(true);
    setError(null);
    try {
      const disc = await startDiscussion(matchId, forceRefresh);
      if (disc.status === "completed" && !forceRefresh) {
        setDiscussion(disc);
        await loadMessages(disc.id);
        const c = await getConsensus(matchId);
        setConsensus(c);
        return;
      }
      await runDeliberation(disc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动失败");
      stopLive();
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!discussion?.id) return;
    setLoading(true);
    setError(null);
    try {
      const disc = await retryDiscussion(discussion.id);
      await runDeliberation(disc);
    } catch (e) {
      setError(e instanceof Error ? e.message : "重试失败");
      stopLive();
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const boot = async () => {
      try {
        let disc: Discussion | null = null;
        if (initialDiscussionId) {
          try {
            disc = await getDiscussion(initialDiscussionId);
          } catch {
            disc = await getLatestDiscussion(matchId);
          }
        } else if (
          deliberationStatus !== "none" ||
          initialConsensus?.discussion_id
        ) {
          const id = initialConsensus?.discussion_id;
          if (id) {
            disc = await getDiscussion(id);
          } else {
            try {
              disc = await getLatestDiscussion(matchId);
            } catch {
              disc = null;
            }
          }
        }
        if (!disc) return;
        setDiscussion(disc);
        await loadMessages(disc.id);
        if (
          disc.status === "running" ||
          disc.status === "pending" ||
          disc.status === "awaiting_user"
        ) {
          await watchDiscussion(disc);
        }
      } catch {
        /* no prior discussion */
      }
    };
    boot();
    return () => stopLive();
  }, [
    initialDiscussionId,
    initialConsensus?.discussion_id,
    deliberationStatus,
    loadMessages,
    matchId,
    stopLive,
    watchDiscussion,
  ]);

  const artifact = consensus?.artifact;
  const isProcessing =
    discussion?.status === "running" || discussion?.status === "pending";
  const canUserInput =
    !isProcessing &&
    (discussion?.status === "awaiting_user" || discussion?.status === "completed");
  const inputPlaceholder = isProcessing
    ? "专家分析中，请稍候…"
    : discussion?.status === "awaiting_user"
      ? "调度官在等待你的回答…"
      : "分析完成后可继续追问各专家…";

  const handleUserSend = async () => {
    const text = userInput.trim();
    if (!text || !discussion?.id || sendingUser) return;
    setSendingUser(true);
    setError(null);
    try {
      const updated =
        discussion.status === "awaiting_user"
          ? await resumeDiscussion(discussion.id, text)
          : await followupChat(discussion.id, text);
      setUserInput("");
      setDiscussion(updated);
      await loadMessages(updated.id);
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
    discussion?.status === "running" ||
    discussion?.status === "pending" ||
    discussion?.status === "awaiting_user";
  const canRetry =
    deliberationStatus === "failed" ||
    discussion?.status === "failed" ||
    deliberationStatus === "partial";

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-bold">AI 战术室合议</h2>
        <span className="text-xs text-slate-500">
          调度官编排各专家；分析中可向你提问，完成后可继续追问
        </span>
      </div>

      <MarketSnapshotStrip market={initialMarket} />

      {discussion && (
        <PhaseProgressBar phase={discussion.phase} round={discussion.round} />
      )}

      {showChat && (
        <div className="mb-4">
          <ChatRoom
            messages={messages}
            isLive={isLive}
            analyzingRole={analyzingRole}
            liveToolCalls={liveToolCalls}
            input={
              discussion && (canUserInput || isProcessing) ? (
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
          {discussion && (
            <button
              type="button"
              onClick={handleRetry}
              disabled={loading}
              className="mt-3 rounded-lg bg-red-600 px-4 py-1.5 text-sm text-white hover:bg-red-500 disabled:opacity-50"
            >
              {loading ? "重新生成中…" : "重新生成合议"}
            </button>
          )}
        </div>
      )}

      {artifact && (
        <>
          <ConsensusCertificate data={artifact} />
          <PlaysRecommendation data={artifact} />
          <MarketEdgeTable edges={artifact.market_edge} />
          <MinorityOpinions opinions={artifact.minority_opinions} />
        </>
      )}

      {deliberationStatus === "none" && !discussion && !loading && (
        <div className="rounded-xl border border-dashed border-pitch-600 p-6 text-center">
          <p className="mb-2 text-slate-300">开始战术室合议</p>
          <p className="mb-4 text-sm text-slate-500">
            预计 10–30 分钟；下方群聊区将实时显示各角色中文讨论
          </p>
          <button
            type="button"
            onClick={() => handleStart(false)}
            disabled={loading}
            className="rounded-lg bg-pitch-500 px-6 py-2 font-medium text-white hover:bg-pitch-400 disabled:opacity-50"
          >
            {loading ? "启动中…" : "开始战术室合议"}
          </button>
        </div>
      )}

      {(deliberationStatus === "ready" || deliberationStatus === "partial") && !isLive && (
        <button
          type="button"
          onClick={() => handleStart(true)}
          disabled={loading}
          className="mb-4 text-sm text-pitch-400 underline hover:text-pitch-300"
        >
          {loading ? "生成中…" : "重新生成合议（强制刷新）"}
        </button>
      )}

      {canRetry && !error && discussion && (
        <button
          type="button"
          onClick={handleRetry}
          disabled={loading}
          className="mb-4 text-sm text-pitch-400 underline"
        >
          重新生成
        </button>
      )}

      {messages.length > 0 && !isLive && (
        <>
          <DisagreementRadar messages={messages} />
          <ReadModeToggle mode={readMode} onChange={setReadMode} />
          <p className="mb-2 text-xs text-slate-500">按阶段折叠查看</p>
          <MessageTimeline messages={messages} readMode={readMode} />
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
