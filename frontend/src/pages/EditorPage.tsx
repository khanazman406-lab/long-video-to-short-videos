import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import ExportDialog, { type ExportOptions } from "../components/ExportDialog";
import ScoreBadge from "../components/ScoreBadge";
import TrimTimeline from "../components/TrimTimeline";
import VideoPlayer from "../components/VideoPlayer";
import { ApiError, api } from "../lib/api";
import { formatTimePrecise, parseTimeInput } from "../lib/utils";

export default function EditorPage() {
  const { videoId, clipId } = useParams<{ videoId: string; clipId: string }>();
  const [start, setStart] = useState(0);
  const [end, setEnd] = useState(0);
  const [title, setTitle] = useState("");
  const [current, setCurrent] = useState(0);
  const [startText, setStartText] = useState("");
  const [endText, setEndText] = useState("");
  const [saving, setSaving] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [download, setDownload] = useState("");

  const clipQuery = useQuery({
    queryKey: ["clip", clipId],
    queryFn: () => api.getClip(clipId!),
    enabled: !!clipId,
  });
  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => api.getVideo(videoId!),
    enabled: !!videoId,
  });

  const clip = clipQuery.data;
  const video = videoQuery.data;

  useEffect(() => {
    if (clip) {
      setStart(clip.start_time);
      setEnd(clip.end_time);
      setTitle(clip.title || "");
      setStartText(formatTimePrecise(clip.start_time));
      setEndText(formatTimePrecise(clip.end_time));
    }
  }, [clip?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  function onTrim(s: number, e: number) {
    setStart(Math.round(s * 100) / 100);
    setEnd(Math.round(e * 100) / 100);
    setStartText(formatTimePrecise(s));
    setEndText(formatTimePrecise(e));
  }

  function applyText(which: "start" | "end") {
    const raw = which === "start" ? startText : endText;
    const parsed = parseTimeInput(raw);
    if (parsed === null || !video) {
      setError(`Couldn't parse "${raw}". Use MM:SS or seconds.`);
      return;
    }
    const clamped = Math.min(Math.max(0, parsed), video.duration);
    if (which === "start") onTrim(Math.min(clamped, end - 1), end);
    else onTrim(start, Math.max(clamped, start + 1));
    setError("");
  }

  async function save() {
    if (!clip) return;
    setSaving(true);
    setError("");
    setNotice("");
    try {
      const updated = await api.updateClip(clip.id, { start_time: start, end_time: end, title });
      clipQuery.refetch();
      setNotice(`Saved — clip is now ${updated.duration.toFixed(1)}s.`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    if (!clip) return;
    onTrim(clip.start_time, clip.end_time);
    setTitle(clip.title || "");
    setNotice("");
  }

  async function confirmExport(opts: ExportOptions) {
    if (!clip) return;
    setExportBusy(true);
    setError("");
    try {
      // Save trim first so the export matches the preview.
      await api.updateClip(clip.id, { start_time: start, end_time: end, title });
      const job = await api.exportClip(clip.id, opts);
      setShowExport(false);
      setNotice("Export started — rendering in the background. Polling for completion…");
      const deadline = Date.now() + 30 * 60 * 1000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 2500));
        const st = await api.getExport(job.id);
        if (st.status === "completed") {
          setDownload(api.fileUrl(st.download_url));
          setNotice("Export complete — your clip is ready.");
          break;
        }
        if (st.status === "failed") {
          setError(st.error_message || "Export failed.");
          break;
        }
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Export failed to start.");
    } finally {
      setExportBusy(false);
    }
  }

  if (clipQuery.isLoading || videoQuery.isLoading)
    return <div className="card animate-pulse-soft p-10 text-center">Loading editor…</div>;
  if (!clip || !video)
    return (
      <div className="card p-10 text-center">
        <p className="font-semibold">Clip not found.</p>
        <Link to="/" className="btn-secondary mt-4">
          Back to Dashboard
        </Link>
      </div>
    );

  const dirty =
    Math.abs(start - clip.start_time) > 0.01 ||
    Math.abs(end - clip.end_time) > 0.01 ||
    title !== (clip.title || "");

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to={`/v/${videoId}/results`} className="text-sm text-brand-600 hover:underline">
            ← Back to results
          </Link>
          <h1 className="mt-1 text-2xl font-bold">Edit #{String(clip.rank).padStart(2, "0")}</h1>
        </div>
        <ScoreBadge score={clip.score} size="lg" />
      </div>

      {notice && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
          {notice}{" "}
          {download && (
            <a href={download} download className="font-semibold underline">
              ⬇ Download now
            </a>
          )}
        </div>
      )}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-5">
        <div className="flex flex-col gap-4 lg:col-span-3">
          <VideoPlayer
            src={api.streamUrl(video.id)}
            startTime={start}
            endTime={end}
            loopSegment
            onTimeUpdate={setCurrent}
          />
          <div className="card p-4">
            <TrimTimeline duration={video.duration} start={start} end={end} currentTime={current} onChange={onTrim} />
          </div>
        </div>

        <div className="flex flex-col gap-4 lg:col-span-2">
          <div className="card p-5">
            <h3 className="font-semibold">Clip settings</h3>
            <label className="mt-3 block text-xs font-medium text-slate-500">Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="input mt-1" maxLength={120} />
            <div className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-500">Start (MM:SS)</label>
                <input
                  value={startText}
                  onChange={(e) => setStartText(e.target.value)}
                  onBlur={() => applyText("start")}
                  onKeyDown={(e) => e.key === "Enter" && applyText("start")}
                  className="input mt-1 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500">End (MM:SS)</label>
                <input
                  value={endText}
                  onChange={(e) => setEndText(e.target.value)}
                  onBlur={() => applyText("end")}
                  onKeyDown={(e) => e.key === "Enter" && applyText("end")}
                  className="input mt-1 font-mono"
                />
              </div>
            </div>
            <p className="mt-2 font-mono text-sm">
              Duration: <strong>{(end - start).toFixed(1)}s</strong>
            </p>
            <div className="mt-4 flex gap-2">
              <button onClick={save} disabled={saving || !dirty} className="btn-primary flex-1">
                {saving ? "Saving…" : "Save changes"}
              </button>
              <button onClick={reset} disabled={!dirty} className="btn-secondary">
                Reset
              </button>
            </div>
            <button onClick={() => setShowExport(true)} className="btn-primary mt-2 w-full !bg-violet-600 hover:!bg-violet-700">
              ⬇ Export this clip
            </button>
          </div>

          <div className="card p-5">
            <h3 className="font-semibold">Why this clip scored highly</h3>
            {clip.reasons.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">No strong signals — a calm section of video.</p>
            ) : (
              <ul className="mt-2 flex flex-col gap-1 text-sm">
                {clip.reasons.map((r) => (
                  <li key={r}>✓ {r}</li>
                ))}
              </ul>
            )}
            {Object.keys(clip.signals || {}).length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-medium text-slate-500">Signal breakdown</p>
                <div className="mt-1.5 flex flex-col gap-1.5">
                  {Object.entries(clip.signals).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-2 text-xs">
                      <span className="w-32 truncate text-slate-500">{k.replace(/_/g, " ")}</span>
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
                        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.round(v * 100)}%` }} />
                      </div>
                      <span className="w-8 text-right font-mono">{Math.round(v * 100)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {showExport && (
        <ExportDialog
          title={`Export Clip ${String(clip.rank).padStart(2, "0")}`}
          busy={exportBusy}
          onCancel={() => setShowExport(false)}
          onConfirm={confirmExport}
        />
      )}
    </div>
  );
}
