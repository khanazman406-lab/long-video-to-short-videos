import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Uploader from "../components/Uploader";
import { ApiError, api } from "../lib/api";
import type { Video } from "../lib/types";
import { formatBytes, formatTime } from "../lib/utils";

const PRESETS = [15, 30, 60];

export default function UploadPage() {
  const navigate = useNavigate();
  const [video, setVideo] = useState<Video | null>(null);
  const [preset, setPreset] = useState<number | "custom">(30);
  const [custom, setCustom] = useState("45");
  const [numClips, setNumClips] = useState("10");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const clipDuration = preset === "custom" ? Number(custom) || 0 : preset;

  async function startAnalysis() {
    if (!video) return;
    const dur = Math.min(Math.max(clipDuration, 5), 180);
    const n = Math.min(Math.max(Number(numClips) || 10, 1), 20);
    if (!dur) {
      setError("Please enter a valid custom duration (5–180 seconds).");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.analyze(video.id, dur, n);
      navigate(`/v/${video.id}/processing`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start analysis.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold">Upload Video</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Upload a long video — ClipForge AI will analyze it and pick the best short moments.
        </p>
      </div>

      {!video ? (
        <div className="card p-6">
          <Uploader onUploaded={setVideo} />
        </div>
      ) : (
        <div className="card flex flex-col gap-5 p-6">
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="w-full shrink-0 overflow-hidden rounded-xl bg-slate-900 sm:w-56">
              {video.thumbnail_url ? (
                <img src={api.fileUrl(video.thumbnail_url)} alt="" className="aspect-video w-full object-cover" />
              ) : (
                <div className="flex aspect-video items-center justify-center text-4xl">🎬</div>
              )}
            </div>
            <div className="text-sm">
              <p className="font-semibold">{video.original_filename}</p>
              <p className="mt-1 text-slate-500 dark:text-slate-400">
                {formatBytes(video.file_size)} · {formatTime(video.duration)}
                {video.width > 0 && ` · ${video.width}×${video.height}`}
                {video.video_codec && ` · ${video.video_codec}`}
              </p>
              <button onClick={() => setVideo(null)} className="btn-secondary mt-3 !py-1.5 text-xs">
                Choose a different video
              </button>
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium">Clip length</p>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p}
                  onClick={() => setPreset(p)}
                  className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
                    preset === p
                      ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-brand-700/20"
                      : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
                  }`}
                >
                  {p}s
                </button>
              ))}
              <button
                onClick={() => setPreset("custom")}
                className={`rounded-xl border px-4 py-2 text-sm font-medium transition ${
                  preset === "custom"
                    ? "border-brand-500 bg-brand-50 ring-1 ring-brand-500 dark:bg-brand-700/20"
                    : "border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
                }`}
              >
                Custom
              </button>
              {preset === "custom" && (
                <input
                  value={custom}
                  onChange={(e) => setCustom(e.target.value)}
                  inputMode="numeric"
                  className="input !w-28"
                  placeholder="seconds"
                  aria-label="Custom duration in seconds"
                />
              )}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              5–180 seconds. Each clip is intelligently centered on its engagement moment.
            </p>
          </div>

          <div>
            <p className="mb-2 text-sm font-medium">Number of clips</p>
            <input
              value={numClips}
              onChange={(e) => setNumClips(e.target.value)}
              inputMode="numeric"
              className="input !w-28"
              aria-label="Number of clips"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
              {error}
            </div>
          )}

          <button onClick={startAnalysis} disabled={busy} className="btn-primary">
            {busy ? "Starting analysis…" : `🔍 Analyze & Generate Top ${numClips || 10} Clips`}
          </button>
        </div>
      )}
    </div>
  );
}
