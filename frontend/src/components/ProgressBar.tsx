export default function ProgressBar({ progress, message }: { progress: number; message?: string }) {
  const pct = Math.max(0, Math.min(100, progress));
  return (
    <div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-brand-500 to-violet-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-1 flex justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>{message || "Working…"}</span>
        <span className="font-mono">{pct.toFixed(0)}%</span>
      </div>
    </div>
  );
}
