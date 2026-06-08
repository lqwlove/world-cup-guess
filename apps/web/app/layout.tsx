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
        <header className="border-b border-pitch-700 bg-pitch-800/80 px-4 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-6xl items-center justify-between">
            <a href="/" className="text-lg font-bold text-gold-400">
              世界杯 AI 战术室
            </a>
            <span className="text-xs text-slate-400">
              2026 美加墨 · 研究工具
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
          {children}
        </main>
        <DisclaimerFooter />
      </body>
    </html>
  );
}
