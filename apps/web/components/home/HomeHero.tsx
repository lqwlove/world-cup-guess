"use client";

import { useEffect, useState } from "react";
import {
  AGENT_BY_ROLE,
  AGENT_PERSONAS,
  DEMO_BRAINSTORM,
  type DemoChatMessage,
} from "@/lib/agents";

const MSG_TYPE_STYLES: Record<string, string> = {
  开场: "bg-amber-500/20 text-amber-300",
  陈述: "bg-sky-500/15 text-sky-300",
  质疑: "bg-rose-500/20 text-rose-300",
  回应: "bg-violet-500/15 text-violet-300",
  结论: "bg-pitch-500/25 text-pitch-300",
};

function ChatBubble({ msg, isNew }: { msg: DemoChatMessage; isNew: boolean }) {
  const agent = AGENT_BY_ROLE[msg.role];
  return (
    <div
      className={`flex gap-3 transition-all duration-500 ${
        isNew ? "animate-message-in opacity-100" : "opacity-90"
      }`}
    >
      <div
        className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-lg shadow-lg ring-2 ${agent.ringClass} ${agent.avatarClass}`}
        title={agent.label}
      >
        {agent.emoji}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-slate-100">
            {agent.label}
          </span>
          <span
            className={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
              MSG_TYPE_STYLES[msg.msgType] || "bg-slate-700 text-slate-400"
            }`}
          >
            {msg.msgType}
          </span>
        </div>
        <p className="rounded-2xl rounded-tl-sm border border-white/5 bg-white/[0.04] px-3.5 py-2.5 text-sm leading-relaxed text-slate-300 backdrop-blur-sm">
          {msg.text}
        </p>
      </div>
    </div>
  );
}

function TypingDots() {
  return (
    <div className="flex items-center gap-3 px-1 py-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-pitch-700/80 text-xs text-slate-500">
        ···
      </div>
      <div className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-bounce rounded-full bg-pitch-400/60"
            style={{ animationDelay: `${i * 150}ms` }}
          />
        ))}
      </div>
    </div>
  );
}

export function HomeHero() {
  const [visibleCount, setVisibleCount] = useState(1);
  const [typing, setTyping] = useState(false);
  const [activeAgent, setActiveAgent] = useState(0);

  useEffect(() => {
    let paused = false;
    const cycle = () => {
      if (paused) return;
      setVisibleCount((c) => {
        if (c >= DEMO_BRAINSTORM.length) {
          paused = true;
          setTyping(false);
          setTimeout(() => {
            setVisibleCount(1);
            setActiveAgent(0);
            paused = false;
          }, 2500);
          return c;
        }
        setTyping(true);
        setActiveAgent(c);
        setTimeout(() => setTyping(false), 600);
        return c + 1;
      });
    };

    const id = setInterval(cycle, 2800);
    return () => clearInterval(id);
  }, []);

  const visible = DEMO_BRAINSTORM.slice(0, visibleCount).slice(-5);

  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 top-0 h-96 w-96 rounded-full bg-pitch-400/15 blur-[100px]" />
        <div className="absolute -right-24 top-1/3 h-80 w-80 rounded-full bg-gold-500/10 blur-[90px]" />
        <div className="absolute bottom-0 left-1/3 h-64 w-64 rounded-full bg-violet-600/10 blur-[80px]" />
        <div className="hero-grid absolute inset-0 opacity-[0.35]" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-pitch-900/20 to-pitch-900" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 pb-16 pt-4 sm:px-6 sm:pb-20 sm:pt-8">
        <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-12">
          <div className="order-2 lg:order-1">
            <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-pitch-500/30 bg-pitch-800/50 px-3 py-1.5 text-xs text-pitch-300 backdrop-blur-sm">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-pitch-400 opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-pitch-400" />
              </span>
              8 位 AI 专家 · 实时战术室合议
            </div>

            <h1 className="text-4xl font-black leading-[1.1] tracking-tight text-white sm:text-5xl lg:text-[3.25rem]">
              <span className="block">不是一个人猜球，</span>
              <span className="mt-1 block bg-gradient-to-r from-pitch-300 via-gold-400 to-pitch-300 bg-clip-text text-transparent">
                是一场 AI 头脑风暴
              </span>
            </h1>

            <p className="mt-5 max-w-lg text-base leading-relaxed text-slate-400 sm:text-lg">
              数据官、阵容官、市场官、风控官……多角色在战术室里
              <span className="text-slate-300"> 质疑、反驳、表决 </span>
              ，像真实群聊一样碰撞观点，最终给出明确预测结论。
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <a
                href="#schedule"
                className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-pitch-500 to-pitch-400 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-pitch-500/25 transition hover:brightness-110"
              >
                进入赛程 · 发起合议
                <span className="transition group-hover:translate-x-0.5">→</span>
              </a>
              <a
                href="#agents"
                className="inline-flex items-center gap-2 rounded-xl border border-pitch-600/80 bg-pitch-800/40 px-5 py-3 text-sm font-medium text-slate-300 backdrop-blur-sm transition hover:border-pitch-500/50 hover:text-white"
              >
                认识专家团队
              </a>
            </div>

            <dl className="mt-10 grid grid-cols-3 gap-4 border-t border-pitch-700/50 pt-8">
              {[
                { n: "8", label: "专家 Agent" },
                { n: "10+", label: "轮交叉辩论" },
                { n: "实时", label: "群聊式回放" },
              ].map((s) => (
                <div key={s.label}>
                  <dt className="text-2xl font-bold text-gold-400 sm:text-3xl">
                    {s.n}
                  </dt>
                  <dd className="mt-0.5 text-xs text-slate-500 sm:text-sm">
                    {s.label}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="order-1 lg:order-2">
            <div className="relative mx-auto max-w-md lg:max-w-none">
              <div className="absolute -inset-4 rounded-3xl bg-gradient-to-br from-pitch-500/20 via-transparent to-gold-500/10 blur-2xl" />

              <div className="agent-orbit pointer-events-none absolute inset-0 hidden sm:block">
                {AGENT_PERSONAS.map((agent, i) => {
                  const angle = (i / AGENT_PERSONAS.length) * 360 - 90;
                  const rad = (angle * Math.PI) / 180;
                  const rx = 48 + Math.cos(rad) * 42;
                  const ry = 48 + Math.sin(rad) * 42;
                  const isActive =
                    visibleCount > 0 &&
                    DEMO_BRAINSTORM[Math.min(visibleCount - 1, DEMO_BRAINSTORM.length - 1)]
                      ?.role === agent.role;
                  return (
                    <div
                      key={agent.role}
                      className="absolute"
                      style={{
                        left: `${rx}%`,
                        top: `${ry}%`,
                        transform: "translate(-50%, -50%)",
                      }}
                    >
                      <div
                        className={`flex h-11 w-11 items-center justify-center rounded-2xl text-lg shadow-xl ring-2 transition-all duration-500 ${
                          agent.avatarClass
                        } ${agent.ringClass} ${
                          isActive
                            ? "scale-110 animate-agent-pulse z-10"
                            : "scale-90 opacity-70"
                        }`}
                        title={agent.label}
                      >
                        {agent.emoji}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-pitch-950/70 shadow-2xl shadow-black/40 backdrop-blur-xl">
                <div className="flex items-center gap-2 border-b border-white/5 bg-pitch-900/80 px-4 py-3">
                  <div className="flex gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500/80" />
                    <span className="h-2.5 w-2.5 rounded-full bg-pitch-400/80" />
                  </div>
                  <span className="flex-1 text-center text-xs font-medium text-slate-500">
                    战术室 · 巴西 vs 阿根廷
                  </span>
                  <span className="rounded bg-pitch-500/20 px-2 py-0.5 text-[10px] font-medium text-pitch-300">
                    LIVE
                  </span>
                </div>

                <div className="relative max-h-[22rem] space-y-4 overflow-hidden p-4 sm:max-h-[26rem] sm:p-5">
                  <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-8 bg-gradient-to-b from-pitch-950/90 to-transparent" />
                  {visible.map((msg, i) => (
                    <ChatBubble
                      key={`${msg.role}-${i}`}
                      msg={msg}
                      isNew={i === visible.length - 1}
                    />
                  ))}
                  {typing && activeAgent < AGENT_PERSONAS.length && (
                    <TypingDots />
                  )}
                </div>

                <div className="border-t border-white/5 bg-pitch-900/50 px-4 py-2.5">
                  <p className="text-center text-[11px] text-slate-600">
                    调度官编排 · 交叉质询 · 最终表决
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
