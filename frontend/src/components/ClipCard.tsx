import { Link } from "react-router-dom";
import { api } from "../lib/api";
import type { Clip } from "../lib/types";
import { formatTimePrecise } from "../lib/utils";
import ScoreBadge from "./ScoreBadge";

interface Props {
  clip: Clip;
  selected?: boolean;
  onToggleSelect?: (id: string) => void;
  onPreview: (clip: Clip) => void;
  onExport: (clip: Clip) => void;
}

export default function ClipCard({ clip, selected, onToggleSelect, onPreview, onExport }: Props) {
  return (
    <div className={`card overflow-hidden transition ${selected ? "ring-2 ring-brand-500" : ""}`}>
      <div className="relative aspect-video bg-slate-900">
        {clip.thumbnail_url ? (
          <img src={api.fileUrl(clip.thumbnail_url)} alt={clip.title} className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full items-center justify-center text-4xl">🎞️</div>
        )}
        <span className="absolute left-2 top-2 rounded-lg bg-black/70 px-2 py-1 font-mono text-xs font-bold text-white">
          #{String(clip.rank).padStart(2, "0")}
        </span>
        <button
          onClick={() => onPreview(clip)}
          className="absolute inset-0 flex items-center justify-center bg-black/0 opacity-0 transition hover:bg-black/30 hover:opacity-100"
          title="Preview clip"
        >
          <span className="rounded-full bg-white/90 px-5 py-2 text-lg">▶</span>
        </button>
        {onToggleSelect && (
          <input
            type="checkbox"
            checked={!!selected}
            onChange={() => onToggleSelect(clip.id)}
            className="absolute right-2 top-2 h-5 w-5 cursor-pointer accent-indigo-600"
            title="Select for batch export"
          />
        )}
      </div>
      <div className="flex flex-col gap-2 p-4">
        <div className="flex items-center justify-between gap-2">
          <ScoreBadge score={clip.score} size="sm" />
          <span className="font-mono text-xs text-slate-500 dark:text-slate-400">
            {formatTimePrecise(clip.start_time)} → {formatTimePrecise(clip.end_time)}
          </span>
        </div>
        <p className="text-sm font-medium">{clip.duration.toFixed(1)} seconds</p>
        {clip.reasons.length > 0 && (
          <ul className="text-xs text-slate-600 dark:text-slate-300">
            {clip.reasons.slice(0, 4).map((r) => (
              <li key={r}>✓ {r}</li>
            ))}
          </ul>
        )}
        <div className="mt-1 flex gap-2">
          <button onClick={() => onPreview(clip)} className="btn-secondary flex-1 !py-1.5 text-xs">
            Preview
          </button>
          <Link to={`/v/${clip.video_id}/edit/${clip.id}`} className="btn-secondary flex-1 !py-1.5 text-xs">
            Edit
          </Link>
          <button onClick={() => onExport(clip)} className="btn-primary flex-1 !py-1.5 text-xs">
            Export
          </button>
        </div>
      </div>
    </div>
  );
}
