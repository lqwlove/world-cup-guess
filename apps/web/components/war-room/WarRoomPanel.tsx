"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getConsensus,
  getDiscussion,
  getMessages,
  runDiscussionSync,
  startDiscussion,
  streamDiscussion,
  submitFeedback,
  getSessionId,
} from "@/lib/api";
import type { ConsensusArtifact, Discussion, DiscussionMessage } from "@/lib/types";
import { PhaseProgressBar } from "./PhaseProgressBar";
import { MessageTimeline } from "./MessageTimeline";
import { ConsensusCertificate, PlaysRecommendation } from "./ConsensusCertificate";
import { MarketEdgeTable } from "./MarketEdgeTable";
import { MinorityOpinions } from "./MinorityOpinions";
import { ReadModeToggle, type ReadMode } from "./ReadModeToggle";
import { DisagreementRadar } from "./DisagreementRadar";

export function WarRoomPanel({
  matchId,
  initialConsensus,
  deliberationStatus,
}: {
  matchId: string;
  initialConsensus: ConsensusArtifact | null;
  deliberationStatus: string;
}) {
  const [consensus, setConsensus] = useState(initialConsensus);
  const [discussion, setDiscussion] = useState<Discussion | null>(null);
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [readMode, setReadMode] = useState<ReadMode>(
    deliberationStatus === "ready" ? "consensus" : "full"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [feedbackSent, setFeedbackSent] = useState(false);

  const loadMessages = useCallback(async (discussionId: string, fromSeq = 0) => {
    const msgs = await getMessages(discussionId, fromSeq);
    if (fromSeq > 0) {
      setMessages((prev) => [...prev, ...msgs.filter((m) => !prev.some((p) => p.seq === m.seq))]);
    } else {
      setMessages(msgs);
    }
  }, []);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      const disc = await startDiscussion(matchId);
      setDiscussion(disc);
      if (disc.status === "completed") {
        const c = await getConsensus(matchId);
        setConsensus(c);
        return;
      }
      // Dev-friendly: run sync if worker unavailable
      try {
        const updated = await runDiscussionSync(disc.id);
        setDiscussion(updated);
        await loadMessages(disc.id);
        const c = await getConsensus(matchId);
        setConsensus(c);
      } catch {
        const es = streamDiscussion(disc.id, async (evt) => {
          const e = evt as { type?: string; seq?: number };
          if (e.type === "message" || e.type === "status") {
            await loadMessages(disc.id);
            const d = await getDiscussion(disc.id);
            setDiscussion(d);
          }
          if (e.type === "consensus") {
            const c = await getConsensus(matchId);
            setConsensus(c);
          }
        });
        setTimeout(() => es.close(), 120000);
        await loadMessages(disc.id);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "启动失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialConsensus?.discussion_id) {
      loadMessages(initialConsensus.discussion_id).catch(() => {});
    }
  }, [initialConsensus, loadMessages]);

  const artifact = consensus?.artifact;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-bold">AI 战术室合议</h2>
        <span className="text-xs text-slate-500">多角色 AI 讨论，非真人聊天</span>
      </div>

      {discussion && (
        <PhaseProgressBar phase={discussion.phase} round={discussion.round} />
      )}

      {artifact && (
        <>
          <ConsensusCertificate data={artifact} />
          <PlaysRecommendation data={artifact} />
          <MarketEdgeTable edges={artifact.market_edge} />
          <MinorityOpinions opinions={artifact.minority_opinions} />
        </>
      )}

      {!artifact && deliberationStatus === "none" && (
        <div className="rounded-xl border border-dashed border-pitch-600 p-6 text-center">
          <p className="mb-2 text-slate-300">开始战术室合议</p>
          <p className="mb-4 text-sm text-slate-500">预计耗时约 10–30 分钟（视讨论深度而定）</p>
          <button
            type="button"
            onClick={handleStart}
            disabled={loading}
            className="rounded-lg bg-pitch-500 px-6 py-2 font-medium text-white hover:bg-pitch-400 disabled:opacity-50"
          >
            {loading ? "合议进行中…" : "开始战术室合议"}
          </button>
        </div>
      )}

      {deliberationStatus === "ready" && !discussion && (
        <button
          type="button"
          onClick={handleStart}
          className="mb-4 text-sm text-pitch-400 underline"
        >
          重新生成合议
        </button>
      )}

      {error && <p className="mb-2 text-sm text-red-400">{error}</p>}

      {messages.length > 0 && (
        <>
          <DisagreementRadar messages={messages} />
          <ReadModeToggle mode={readMode} onChange={setReadMode} />
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
