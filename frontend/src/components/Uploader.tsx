import { useRef, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Video } from "../lib/types";
import { formatBytes } from "../lib/utils";

interface Props {
  onUploaded: (video: Video) => void;
}

const ACCEPT = ".mp4,.mov,.webm,.mkv,.m4v,video/mp4,video/quicktime,video/webm,video/x-matroska";

export default function Uploader({ onUploaded }: Props) {
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [fileInfo, setFileInfo] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File | undefined) {
    if (!file || progress !== null) return;
    setError("");
    setFileInfo(`${file.name} · ${formatBytes(file.size)}`);
    setProgress(1);
    try {
      const video = await api.uploadVideo(file, setProgress);
      onUploaded(video);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed. Please try again.");
      setProgress(null);
    }
  }

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFile(e.dataTransfer.files?.[0]);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed px-6 py-14 text-center transition ${
          dragging
            ? "border-brand-500 bg-brand-50 dark:bg-brand-700/10"
            : "border-slate-300 hover:border-brand-400 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-900"
        }`}
      >
        <div className="text-5xl">🎬</div>
        <div>
          <p className="text-lg font-semibold">Drag &amp; Drop Video Here</p>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            or click to browse · MP4, MOV, WebM, MKV
          </p>
        </div>
        <span className="btn-primary">Upload Video</span>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>

      {fileInfo && (
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">📎 {fileInfo}</p>
      )}
      {progress !== null && (
        <div className="mt-3">
          <div className="h-2.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <div
              className="h-full rounded-full bg-brand-600 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-slate-500">Uploading… {progress}%</p>
        </div>
      )}
      {error && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </div>
      )}
    </div>
  );
}
