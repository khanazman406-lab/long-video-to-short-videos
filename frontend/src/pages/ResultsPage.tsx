import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import ClipCard from "../components/ClipCard";
import EmptyState from "../components/EmptyState";
import ExportDialog, { type ExportOptions } from "../components/ExportDialog";
import ProgressBar from "../components/ProgressBar";
import VideoPlayer from "../components/VideoPlayer";
import { ApiError, api } from "../lib/api";
import type { Clip, ExportJob } from "../lib/types";

export default function ResultsPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [preview, setPreview] = useState<Clip | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [exportTarget, setExportTarget] = useState<Clip | "all" | null>(null);
  const [exportBusy, setExportBusy] = useState(false);
  const [exports, setExports] = useState<ExportJob[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const pollRef = useRef<number | null>(null);

  const clipsQuery = useQuery({
    queryKey: ["clips", videoId],
    queryFn: () => api.listClips(videoId!),
    enabled: !!videoId,
  });
  const videoQuery = useQuery({
    queryKey: ["video", videoId],
    queryFn: () => api.getVideo(videoId!),
    enabled: !!videoId,
  });

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function startExportPolling() {
    if (pollRef.current) return;
    pollRef.current = window.setInterval(async () => {
      try {
        const list = await api.listExports(videoId!);
        setExports(list.exports);
        const pending = list.exports.some((e) => e.status === "queued" || e.status === "exporting");
        if (!pending && pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
          clipsQuery.refetch();
        }
      } catch {
        /* polling is best-effort */
      }
    }, 2000);
  }

  useEffect(
    () => () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    },
    []
  );

  // Load existing exports on mount.
  useEffect(() => {
    if (!videoId) return;
    api
      .listExports(videoId)
      .then((l) => {
        setExports(l.exports);
        if (l.exports.some((e) => e.status === "queued" || e.status === "exporting")) startExportPolling();
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  async function confirmExport(opts: ExportOptions) {
    if (!exportTarget) return;
    setExportBusy(true);
    setError("");
    try {
      if (exportTarget === "all") {
        const ids = selected.size > 0 ? [...selected] : undefined;
        const list = await api.exportAll(videoId!, { ...opts, clip_ids: ids });
        setExports((prev) => [...prev, ...list.exports]);
        setNotice(`Batch export started for ${list.count} clip${list.count === 1 ? "" : "s"}.`);
      } else {
        const job = await api.exportClip(exportTarget.id, opts);
        setExports((prev) => [...prev, job]);
        setNotice(`Export started for Clip ${String(exportTarget.rank).padStart(2, "0")}.`);
      }
      setExportTarget(null);
      startExportPolling();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Export failed to start.");
    } finally {
      setExportBusy(false);
    }
  }

  if (clipsQuery.isLoading) return <div className="card animate-pulse-soft p-10 text-center">Loading clips…</div>;
  if (clipsQuery.error)
    return (
      <div className="card p-10 text-center">
        <p className="font-semibold">Couldn't load clips.</p>
        <Link to="/" className="btn-secondary mt-4">
          Back to Dashboard
        </Link>
      </div>
    );

  const clips = clipsQuery.data?.clips || [];
  const video = videoQuery.data;
  const doneCount = exports.filter((e) => e.status === "completed").length;
  const pendingCount = exports.filter((e) => e.status === "queued" || e.status === "exporting").length;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Top {clips.length} Clips</h1>
          <p className="mt-1 truncate text-sm text-slate-500 dark:text-slate-400">
            {video?.original_filename} · ranked by Engagement Score
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setExportTarget("all")} className="btn-primary" disabled={clips.length === 0}>
            📦 Export {selected.size > 0 ? `Selected (${selected.size})` : "All"}
          </button>
        </div>
      </div>

      {notice && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-300">
          {notice}
        </div>
      )}
      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}

      {(pendingCount > 0 || exports.length > 0) && (
        <div className="card p-4">
          <p className="mb-2 text-sm font-medium">
            Exports — {doneCount}/{exports.length} complete
            {pendingCount > 0 && ` · Exporting… (${pendingCount} pending)`}
          </p>
          {pendingCount > 0 && (
            <div className="mb-3">
              <ProgressBar progress={(doneCount / Math.max(1, exports.length)) * 100} message={`Exporting ${doneCount + 1}/${exports.length}`} />
            </div>
          )}
          <div className="flex flex-col gap-1.5 text-sm">
            {exports.map((e) => (
              <div key={e.id} className="flex items-center justify-between gap-2 rounded-lg bg-slate-50 px-3 py-1.5 dark:bg-slate-800">
                <span className="truncate">
                  Clip {e.clip_id.slice(0, 6)} · {e.aspect_ratio} {e.output_format.toUpperCase()} · {e.quality}
                </span>
                {e.status === "completed" ? (
                  <a href={api.fileUrl(e.download_url)} download className="font-medium text-brand-600 hover:underline">
                    ⬇ Download
                  </a>
                ) : e.status === "failed" ? (
                  <span className="text-red-600">{e.error_message || "Failed"}</span>
                ) : (
                  <span className="animate-pulse-soft text-slate-500">{e.status}…</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {clips.length === 0 ? (
        <EmptyState
          icon="🔍"
          title="No clips yet"
          body="This video hasn't been analyzed, or analysis produced no clips."
          actionTo={`/v/${videoId}/processing`}
          actionLabel="Check processing status"
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {clips.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              selected={selected.has(clip.id)}
              onToggleSelect={toggleSelect}
              onPreview={setPreview}
              onExport={setExportTarget}
            />
          ))}
        </div>
      )}

      {preview && videoId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={() => setPreview(null)}>
          <div className="w-full max-w-3xl" onClick={(e) => e.stopPropagation()}>
            <VideoPlayer
              src={api.streamUrl(videoId)}
              startTime={preview.start_time}
              endTime={preview.end_time}
              loopSegment
              autoPlay
            />
            <div className="mt-2 flex items-center justify-between gap-2">
              <p className="text-sm font-medium text-white">
                #{String(preview.rank).padStart(2, "0")} · ⚡ {Math.round(preview.score)}/100 ·{" "}
                {preview.duration.toFixed(1)}s
              </p>
              <div className="flex gap-2">
                <Link to={`/v/${videoId}/edit/${preview.id}`} className="btn-secondary !py-1.5 text-xs">
                  Edit
                </Link>
                <button
                  onClick={() => {
                    setExportTarget(preview);
                    setPreview(null);
                  }}
                  className="btn-primary !py-1.5 text-xs"
                >
                  Export
                </button>
                <button onClick={() => setPreview(null)} className="btn-secondary !py-1.5 text-xs">
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {exportTarget && (
        <ExportDialog
          title={exportTarget === "all" ? `Export ${selected.size > 0 ? selected.size : clips.length} clips` : `Export Clip ${String(exportTarget.rank).padStart(2, "0")}`}
          busy={exportBusy}
          onCancel={() => setExportTarget(null)}
          onConfirm={confirmExport}
        />
      )}
    </div>
  );
}
