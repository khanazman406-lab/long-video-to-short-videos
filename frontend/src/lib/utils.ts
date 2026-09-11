export function formatTime(s: number): string {
  if (!isFinite(s) || s < 0) s = 0;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m).padStart(2, "0");
  const ss = sec.toFixed(sec >= 10 && h === 0 && m === 0 ? 1 : 0).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss.padStart(2, "0")}` : `${mm}:${ss}`;
}

export function formatTimePrecise(s: number): string {
  if (!isFinite(s) || s < 0) s = 0;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  const base = `${String(m).padStart(2, "0")}:${sec.toFixed(2).padStart(5, "0")}`;
  return h > 0 ? `${String(h).padStart(2, "0")}:${base}` : base;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    queued: "Queued",
    uploading: "Uploaded",
    extracting: "Extracting",
    analyzing: "Analyzing",
    scoring: "Scoring",
    generating_clips: "Generating clips",
    exporting: "Exporting",
    completed: "Completed",
    failed: "Failed",
    ready: "Ready",
    exported: "Exported",
  };
  return map[status] || status;
}

export function statusColor(status: string): string {
  if (status === "completed" || status === "ready" || status === "exported")
    return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300";
  if (status === "failed") return "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300";
  if (status === "exporting") return "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300";
  return "bg-brand-100 text-brand-700 dark:bg-brand-700/30 dark:text-brand-100";
}

export function parseTimeInput(text: string): number | null {
  // Accepts "SS", "MM:SS", "HH:MM:SS" with optional decimals.
  const parts = text.trim().split(":").map((p) => p.trim());
  if (parts.length > 3 || parts.some((p) => p === "" || isNaN(Number(p)))) return null;
  let total = 0;
  for (const p of parts) total = total * 60 + Number(p);
  return total >= 0 ? total : null;
}
