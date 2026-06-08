import { AGENT_PERSONAS } from "@/lib/agents";

const CAPABILITIES = [
  {
    icon: "💬",
    title: "群聊式辩论",
    desc: "CHALLENGE / REBUTTAL / SUPPORT，观点可追溯、可回放",
  },
  {
    icon: "🔍",
    title: "联网情报",
    desc: "Agent 自主搜索球队近况，补充合议论据",
  },
  {
    icon: "📊",
    title: "市场校准",
    desc: "对接 Polymarket 隐含概率，发现低估与高估",
  },
  {
    icon: "⚡",
    title: "明确结论",
    desc: "多轮合议后输出主胜/平/客胜，不再骑墙",
  },
];

export function AgentShowcase() {
  return (
    <>
      <section id="agents" className="scroll-mt-20 border-t border-pitch-800/80 py-14 sm:py-16">
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">
            你的 AI 专家团
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500 sm:text-base">
            每位 Agent 有鲜明人设与职责，在调度官主持下轮流发言、互相质疑
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {AGENT_PERSONAS.map((agent, i) => (
            <div
              key={agent.role}
              className="group relative overflow-hidden rounded-2xl border border-pitch-700/60 bg-gradient-to-b from-pitch-800/60 to-pitch-900/80 p-4 transition duration-300 hover:-translate-y-1 hover:border-pitch-500/40 hover:shadow-lg hover:shadow-pitch-500/5"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <div className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-white/5 blur-2xl transition group-hover:bg-pitch-400/10" />
              <div className="flex items-start gap-3">
                <div
                  className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl shadow-lg ring-2 ${agent.ringClass} ${agent.avatarClass}`}
                >
                  {agent.emoji}
                </div>
                <div className="min-w-0">
                  <h3 className="font-bold text-slate-100">{agent.label}</h3>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">
                    {agent.tagline}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="pb-14 sm:pb-16">
        <div className="overflow-hidden rounded-2xl border border-pitch-700/50 bg-pitch-800/30">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4">
            {CAPABILITIES.map((cap) => (
              <div
                key={cap.title}
                className="border-b border-pitch-700/40 p-5 last:border-b-0 sm:border-b-0 sm:border-r sm:last:border-r-0"
              >
                <span className="text-2xl">{cap.icon}</span>
                <h3 className="mt-3 font-semibold text-slate-200">{cap.title}</h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-500">
                  {cap.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
