export default function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const s = Math.round(score);
  const color =
    s >= 75
      ? "bg-emerald-500"
      : s >= 50
      ? "bg-amber-500"
      : s >= 25
      ? "bg-orange-500"
      : "bg-slate-400";
  const pad = size === "lg" ? "px-4 py-2 text-xl" : size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full ${color} font-bold text-white ${pad}`} title={`Engagement Score: ${s}/100`}>
      ⚡ {s}
      <span className="font-normal opacity-80">/100</span>
    </span>
  );
}
