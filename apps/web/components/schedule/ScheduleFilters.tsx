"use client";

import { useRouter, useSearchParams } from "next/navigation";

export function ScheduleFilters() {
  const router = useRouter();
  const search = useSearchParams();

  const update = (key: string, value: string) => {
    const params = new URLSearchParams(search.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    router.push(`/?${params.toString()}`);
  };

  return (
    <div className="flex flex-wrap gap-3">
      <select
        className="rounded-lg border border-pitch-700 bg-pitch-800 px-3 py-2 text-sm"
        value={search.get("stage") || ""}
        onChange={(e) => update("stage", e.target.value)}
      >
        <option value="">全部阶段</option>
        <option value="group">小组赛</option>
        <option value="round32">32强</option>
        <option value="round16">16强</option>
        <option value="quarter">8强</option>
        <option value="semifinal">半决赛</option>
        <option value="third_place">三四名</option>
        <option value="final">决赛</option>
      </select>
      <select
        className="rounded-lg border border-pitch-700 bg-pitch-800 px-3 py-2 text-sm"
        value={search.get("group") || ""}
        onChange={(e) => update("group", e.target.value)}
      >
        <option value="">全部小组</option>
        {["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"].map((g) => (
          <option key={g} value={g}>
            小组 {g}
          </option>
        ))}
      </select>
      <input
        type="date"
        className="rounded-lg border border-pitch-700 bg-pitch-800 px-3 py-2 text-sm"
        value={search.get("date") || ""}
        onChange={(e) => update("date", e.target.value)}
      />
    </div>
  );
}
