"use client";

export type ReadMode = "consensus" | "full" | "disagreement";

export function ReadModeToggle({
  mode,
  onChange,
}: {
  mode: ReadMode;
  onChange: (m: ReadMode) => void;
}) {
  const options: { id: ReadMode; label: string }[] = [
    { id: "consensus", label: "只看共识" },
    { id: "full", label: "完整战术室" },
    { id: "disagreement", label: "只看分歧" },
  ];

  return (
    <div className="mb-3 flex gap-2">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          onClick={() => onChange(o.id)}
          className={`rounded-full px-3 py-1 text-xs ${
            mode === o.id
              ? "bg-pitch-500 text-white"
              : "border border-pitch-600 text-slate-400 hover:border-pitch-400"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
