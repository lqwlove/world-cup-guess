import type { Metadata } from "next";
import "./globals.css";
import { DisclaimerFooter } from "@/components/war-room/DisclaimerFooter";

export const metadata: Metadata = {
  title: "世界杯智能预测平台",
  description: "AI 战术室合议 — 赛事研究与信息分析工具",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-50 border-b border-pitch-700/80 bg-pitch-900/85 px-4 py-3.5 backdrop-blur-md">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
            <a href="/" className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-pitch-400 to-pitch-500 text-sm shadow-md shadow-pitch-500/30">
                ⚽
              </span>
              <span className="text-lg font-bold tracking-tight text-gold-400">
                世界杯 AI 战术室
              </span>
            </a>
            <nav className="hidden items-center gap-6 text-sm text-slate-400 sm:flex">
              <a href="/#agents" className="transition hover:text-pitch-300">
                专家团队
              </a>
              <a href="/#schedule" className="transition hover:text-pitch-300">
                赛程
              </a>
            </nav>
            <span className="text-xs text-slate-500 sm:text-slate-400">
              2026 美加墨
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-4 sm:py-6">
          {children}
        </main>
        <DisclaimerFooter />
      </body>
    </html>
  );
}
