import { useState } from "react";
import type { AspectRatio, OutputFormat, Quality } from "../lib/types";

export interface ExportOptions {
  aspect_ratio: AspectRatio;
  output_format: OutputFormat;
  quality: Quality;
}

interface Props {
  title: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: (opts: ExportOptions) => void;
}

const ASPECTS: { id: AspectRatio; label: string; hint: string }[] = [
  { id: "16:9", label: "YouTube", hint: "16:9 landscape" },
  { id: "9:16", label: "TikTok / Reels / Shorts", hint: "9:16 vertical" },
  { id: "1:1", label: "Square", hint: "1:1 square" },
];

const QUALITIES: { id: Quality; label: string; hint: string }[] = [
  { id: "fast", label: "Fast", hint: "smaller file, quicker render" },
  { id: "balanced", label: "Balanced", hint: "recommended" },
  { id: "high", label: "High Quality", hint: "larger file, best detail" },
];

export default function ExportDialog({ title, busy, onCancel, onConfirm }: Props) {
  const [aspect, setAspect] = useState<AspectRatio>("9:16");
  const [format, setFormat] = useState<OutputFormat>("mp4");
  const [quality, setQuality] = useState<Quality>("balanced");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onCancel}>
      <div
        className="card w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label={title}
      >
        <h3 className="text-lg font-semibold">{title}</h3>

        <p className="mb-2 mt-4 text-sm font-medium">Aspect ratio</p>
        <div className="grid grid-cols-3 gap-2">
          {ASPECTS.map((a) => (
            <button
              key={a.id}
              onClick={() => setAspect(a.id)}
              className={`rounded-xl border px-2 py-2.5 text-center transition ${
                aspect === a.id
                  ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-brand-700/20"
                  : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
              }`}
            >
              <span className="block text-sm font-semibold">{a.id}</span>
              <span className="block text-[11px] text-slate-500 dark:text-slate-400">{a.label}</span>
            </button>
          ))}
        </div>

        <p className="mb-2 mt-4 text-sm font-medium">Format</p>
        <div className="grid grid-cols-2 gap-2">
          {(["mp4", "webm"] as OutputFormat[]).map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={`rounded-xl border px-2 py-2 text-sm font-semibold uppercase transition ${
                format === f
                  ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-brand-700/20"
                  : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        <p className="mb-2 mt-4 text-sm font-medium">Quality</p>
        <div className="grid grid-cols-3 gap-2">
          {QUALITIES.map((q) => (
            <button
              key={q.id}
              onClick={() => setQuality(q.id)}
              title={q.hint}
              className={`rounded-xl border px-2 py-2 text-center transition ${
                quality === q.id
                  ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-brand-700/20"
                  : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
              }`}
            >
              <span className="block text-sm font-semibold">{q.label}</span>
              <span className="block text-[11px] text-slate-500 dark:text-slate-400">{q.hint}</span>
            </button>
          ))}
        </div>

        <div className="mt-6 flex gap-2">
          <button onClick={onCancel} className="btn-secondary flex-1" disabled={busy}>
            Cancel
          </button>
          <button
            onClick={() => onConfirm({ aspect_ratio: aspect, output_format: format, quality })}
            className="btn-primary flex-1"
            disabled={busy}
          >
            {busy ? "Starting…" : "Start Export"}
          </button>
        </div>
      </div>
    </div>
  );
}
