import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ProgressBar from "../components/ProgressBar";
import { api } from "../lib/api";
import type { VideoStatus } from "../lib/types";
import { statusColor, statusLabel } from "../lib/utils";

const STAGES = ["queued", "extracting", "analyzing", "scoring", "generating_clips", "completed"];

export default function ProcessingPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const navigate = useNavigate();
  const [status, setStatus] = useState<VideoStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!videoId) return;
    let stopped = false;
    let es: EventSource | null = null;

    // Prefer SSE, fall back to polling if the stream fails.
    try {
      es = new EventSource(`/api/videos/${videoId}/events`);
      es.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          setStatus((prev) => ({ ...(prev as VideoStatus), id: videoId, num_clips: prev?.num_clips ?? 0, ...data }));
          if (data.status === "completed") navigate(`/v/${videoId}/results`);
        } catch {
          /* ignore malformed chunk */
        }
      };
      es.onerror = () => {
        es?.close();
        es = null;
      };
    } catch {
      es = null;
    }

    const poll = async () => {
      if (stopped) return;
      try {
        const s = await api.getStatus(videoId);
        if (!stopped) {
          setStatus(s);
          if (s.status === "completed") {
            navigate(`/v/${videoId}/results`);
            return;
          }
        }
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : "Failed to load status.");
      }
      if (!stopped) setTimeout(poll, es ? 5000 : 2000);
    };
    poll();

    return () => {
      stopped = true;
      es?.close();
    };
  }, [videoId, navigate]);

  if (error)
    return (
      <div className="card mx-auto max-w-xl p-10 text-center">
        <p className="font-semibold">{error}</p>
        <Link to="/" className="btn-secondary mt-4">
          Back to Dashboard
        </Link>
      </div>
    );
  if (!status) return <div className="card animate-pulse-soft p-10 text-center">Connecting…</div>;

  const failed = status.status === "failed";
  const stageIdx = STAGES.indexOf(status.status);

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold">{failed ? "Processing failed" : "Analyzing video…"}</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          {failed ? "Something went wrong — details below." : "Detecting high-engagement moments"}
        </p>
      </div>

      <div className="card p-6">
        {!failed && (
          <div className="mb-4 flex justify-center text-5xl">
            <span className="animate-pulse-soft">🔍</span>
          </div>
        )}
        <ProgressBar progress={status.progress} message={status.stage_message} />
        <div className="mt-4 flex items-center justify-center gap-2">
          <span className={`rounded-full px-3 py-1 text-xs font-medium ${statusColor(status.status)}`}>
            {statusLabel(status.status)}
          </span>
        </div>
        <ol className="mt-5 flex flex-col gap-1.5 text-sm">
          {STAGES.filter((s) => s !== "completed").map((s) => {
            const idx = STAGES.indexOf(s);
            const done = stageIdx > idx || status.status === "completed";
            const active = stageIdx === idx && !failed;
            return (
              <li key={s} className={`flex items-center gap-2 ${active ? "font-semibold" : "text-slate-500"}`}>
                <span>{done ? "✅" : active ? "⏳" : "·"}</span> {statusLabel(s)}
              </li>
            );
          })}
        </ol>
        {failed && (
          <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
            {status.error_message || "We couldn't process this video."}
          </div>
        )}
      </div>

      <div className="flex justify-center gap-3">
        {failed ? (
          <>
            <Link to="/" className="btn-secondary">
              Dashboard
            </Link>
            <Link to="/upload" className="btn-primary">
              Try another video
            </Link>
          </>
        ) : (
          <Link to="/" className="btn-secondary">
            ← Back to Dashboard (processing continues)
          </Link>
        )}
      </div>
    </div>
  );
}
