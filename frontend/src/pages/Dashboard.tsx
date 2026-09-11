import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import ProgressBar from "../components/ProgressBar";
import { BRAND } from "../lib/brand";
import { api } from "../lib/api";
import { formatBytes, formatDate, formatTime, statusColor, statusLabel } from "../lib/utils";

export default function Dashboard() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["videos"],
    queryFn: api.listVideos,
    refetchInterval: 5000,
  });

  if (isLoading)
    return (
      <div className="card animate-pulse-soft p-10 text-center text-slate-500">Loading projects…</div>
    );
  if (error)
    return (
      <div className="card p-10 text-center">
        <p className="font-semibold">Couldn't reach the backend.</p>
        <p className="mt-1 text-sm text-slate-500">
          Make sure the API server is running, then try again.
        </p>
        <button onClick={() => refetch()} className="btn-secondary mt-4">
          Retry
        </button>
      </div>
    );

  const videos = data || [];
  const processing = videos.filter((v) =>
    ["queued", "extracting", "analyzing", "scoring", "generating_clips", "exporting"].includes(v.status)
  );
  const done = videos.filter((v) => v.status === "completed");
  const failed = videos.filter((v) => v.status === "failed");

  return (
    <div className="flex flex-col gap-8">
      <section className="card relative overflow-hidden p-8">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-600/10 via-violet-500/10 to-transparent" />
        <div className="relative">
          <h1 className="text-3xl font-bold">{BRAND.name}</h1>
          <p className="mt-1 text-slate-600 dark:text-slate-300">{BRAND.tagline}</p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link to="/upload" className="btn-primary">
              ⬆ Upload Video
            </Link>
          </div>
        </div>
      </section>

      {processing.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">⚙️ Processing ({processing.length})</h2>
          <div className="grid gap-3">
            {processing.map((v) => (
              <Link key={v.id} to={`/v/${v.id}/processing`} className="card p-4 transition hover:shadow-md">
                <div className="flex items-center justify-between gap-3">
                  <p className="truncate font-medium">{v.original_filename}</p>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${statusColor(v.status)}`}>
                    {statusLabel(v.status)}
                  </span>
                </div>
                <div className="mt-2">
                  <ProgressBar progress={v.progress} message={v.stage_message} />
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      <section>
        <h2 className="mb-3 text-lg font-semibold">✅ Completed Projects ({done.length})</h2>
        {done.length === 0 ? (
          <EmptyState
            icon="✨"
            title="No completed projects yet"
            body="Upload a long video and ClipForge AI will find the best short-clip moments for you."
            actionTo="/upload"
            actionLabel="Upload your first video"
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {done.map((v) => (
              <Link key={v.id} to={`/v/${v.id}/results`} className="card overflow-hidden transition hover:shadow-md">
                <div className="aspect-video bg-slate-900">
                  {v.thumbnail_url ? (
                    <img src={api.fileUrl(v.thumbnail_url)} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full items-center justify-center text-4xl">🎬</div>
                  )}
                </div>
                <div className="p-4">
                  <p className="truncate font-medium" title={v.original_filename}>
                    {v.original_filename}
                  </p>
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                    {formatTime(v.duration)} · {formatBytes(v.file_size)} · {v.num_clips} clips
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{formatDate(v.created_at)}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {failed.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">⚠️ Needs attention ({failed.length})</h2>
          <div className="grid gap-3">
            {failed.map((v) => (
              <Link key={v.id} to={`/v/${v.id}/processing`} className="card border-red-200 p-4 dark:border-red-900">
                <p className="truncate font-medium">{v.original_filename}</p>
                <p className="mt-1 text-sm text-red-600 dark:text-red-400">
                  {v.error_message || "Processing failed."}
                </p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {videos.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">📚 Project History</h2>
          <div className="card overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-700">
                  <th className="px-4 py-3">Project</th>
                  <th className="px-4 py-3">Duration</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Clips</th>
                </tr>
              </thead>
              <tbody>
                {videos.map((v) => (
                  <tr key={v.id} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                    <td className="max-w-[240px] truncate px-4 py-2.5 font-medium">
                      <Link to={v.status === "completed" ? `/v/${v.id}/results` : `/v/${v.id}/processing`} className="hover:underline">
                        {v.original_filename}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5">{formatTime(v.duration)}</td>
                    <td className="px-4 py-2.5 text-slate-500">{formatDate(v.created_at)}</td>
                    <td className="px-4 py-2.5">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${statusColor(v.status)}`}>
                        {statusLabel(v.status)}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">{v.num_clips}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
