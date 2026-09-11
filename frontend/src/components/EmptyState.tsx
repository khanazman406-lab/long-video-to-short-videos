import { Link } from "react-router-dom";

export default function EmptyState({
  icon = "🎬",
  title,
  body,
  actionTo,
  actionLabel,
}: {
  icon?: string;
  title: string;
  body: string;
  actionTo?: string;
  actionLabel?: string;
}) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-14 text-center">
      <div className="text-5xl">{icon}</div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="max-w-md text-sm text-slate-500 dark:text-slate-400">{body}</p>
      {actionTo && actionLabel && (
        <Link to={actionTo} className="btn-primary mt-2">
          {actionLabel}
        </Link>
      )}
    </div>
  );
}
