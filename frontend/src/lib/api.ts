import type {
  AnalyzeResponse,
  Clip,
  ClipList,
  ExportJob,
  ExportList,
  Health,
  Video,
  VideoStatus,
} from "./apiTypes";
import type { AspectRatio, OutputFormat, Quality } from "./types";

const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) message = String(body.detail);
    } catch {
      /* keep default */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  listVideos: () => request<Video[]>("/api/videos"),
  getVideo: (id: string) => request<Video>(`/api/videos/${id}`),
  deleteVideo: (id: string) =>
    request<{ deleted: string }>(`/api/videos/${id}`, { method: "DELETE" }),
  getStatus: (id: string) => request<VideoStatus>(`/api/videos/${id}/status`),
  analyze: (id: string, clip_duration: number, num_clips: number) =>
    request<AnalyzeResponse>(`/api/videos/${id}/analyze`, {
      method: "POST",
      body: JSON.stringify({ clip_duration, num_clips }),
    }),
  listClips: (videoId: string) => request<ClipList>(`/api/videos/${videoId}/clips`),
  getClip: (id: string) => request<Clip>(`/api/clips/${id}`),
  updateClip: (id: string, patch: { start_time?: number; end_time?: number; title?: string }) =>
    request<Clip>(`/api/clips/${id}`, { method: "PUT", body: JSON.stringify(patch) }),
  exportClip: (
    id: string,
    opts: { aspect_ratio: AspectRatio; output_format: OutputFormat; quality: Quality }
  ) => request<ExportJob>(`/api/clips/${id}/export`, { method: "POST", body: JSON.stringify(opts) }),
  exportAll: (
    videoId: string,
    opts: {
      aspect_ratio: AspectRatio;
      output_format: OutputFormat;
      quality: Quality;
      clip_ids?: string[];
    }
  ) =>
    request<ExportList>(`/api/videos/${videoId}/export-all`, {
      method: "POST",
      body: JSON.stringify(opts),
    }),
  listExports: (videoId: string) => request<ExportList>(`/api/videos/${videoId}/exports`),
  getExport: (id: string) => request<ExportJob>(`/api/exports/${id}`),

  streamUrl: (videoId: string) => `${BASE}/api/videos/${videoId}/stream`,
  fileUrl: (path: string) => (path.startsWith("http") ? path : `${BASE}${path}`),
  downloadUrl: (exportId: string) => `${BASE}/api/exports/${exportId}/download`,

  /** Upload with progress via XHR (fetch can't report upload progress). */
  uploadVideo: (file: File, onProgress: (pct: number) => void): Promise<Video> =>
    new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${BASE}/api/videos/upload`);
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) resolve(body as Video);
          else reject(new ApiError(xhr.status, body?.detail || "Upload failed."));
        } catch {
          reject(new ApiError(xhr.status, "Upload failed."));
        }
      };
      xhr.onerror = () => reject(new ApiError(0, "Network error during upload."));
      const form = new FormData();
      form.append("file", file, file.name);
      onProgress(1);
      xhr.send(form);
    }),
};
