import { formatTimePrecise } from "../lib/utils";

interface Props {
  duration: number;
  start: number;
  end: number;
  currentTime?: number;
  onChange: (start: number, end: number) => void;
}

/** START ├──[ selected segment ]──┤ END dual-handle trim control. */
export default function TrimTimeline({ duration, start, end, currentTime, onChange }: Props) {
  const dur = Math.max(duration, 0.01);
  const leftPct = (start / dur) * 100;
  const widthPct = Math.max(0, ((end - start) / dur) * 100);
  const playPct = currentTime !== undefined ? (currentTime / dur) * 100 : null;

  return (
    <div>
      <div className="mb-1 flex justify-between font-mono text-xs text-slate-500 dark:text-slate-400">
        <span>START {formatTimePrecise(start)}</span>
        <span>END {formatTimePrecise(end)}</span>
      </div>
      <div className="relative h-12 rounded-xl bg-slate-200 dark:bg-slate-800">
        <div
          className="absolute top-0 h-full rounded-xl bg-brand-500/25 ring-1 ring-brand-500/50"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
        />
        {playPct !== null && (
          <div
            className="absolute top-0 h-full w-0.5 bg-red-500"
            style={{ left: `${playPct}%` }}
          />
        )}
        <input
          type="range"
          className="trim absolute inset-0 h-full w-full"
          min={0}
          max={dur}
          step={0.1}
          value={start}
          onChange={(e) => onChange(Math.min(Number(e.target.value), end - 1), end)}
          aria-label="Trim start"
        />
        <input
          type="range"
          className="trim absolute inset-0 h-full w-full"
          min={0}
          max={dur}
          step={0.1}
          value={end}
          onChange={(e) => onChange(start, Math.max(Number(e.target.value), start + 1))}
          aria-label="Trim end"
        />
      </div>
      <div className="mt-1 flex justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>0:00</span>
        <span>
          Selected {(end - start).toFixed(1)}s of {dur.toFixed(1)}s
        </span>
        <span>{formatTimePrecise(dur)}</span>
      </div>
    </div>
  );
}
