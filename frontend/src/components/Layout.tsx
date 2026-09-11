import { useEffect, useState } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { BRAND } from "../lib/brand";

function ThemeToggle() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("clipforge-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    const saved = localStorage.getItem("clipforge-theme");
    if (saved === "dark") setDark(true);
    else if (saved === "light") setDark(false);
    else if (window.matchMedia("(prefers-color-scheme: dark)").matches) setDark(true);
  }, []);
  return (
    <button
      onClick={() => setDark((d) => !d)}
      className="btn-secondary !px-3"
      title={dark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {dark ? "☀️" : "🌙"}
    </button>
  );
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const link = (to: string, label: string) => (
    <NavLink
      key={to}
      to={to}
      className={({ isActive }) =>
        `rounded-lg px-3 py-2 text-sm font-medium transition ${
          isActive || (to === "/upload" && location.pathname.startsWith("/v/"))
          ? "bg-brand-600/10 text-brand-700 dark:text-brand-100"
          : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
        }`
      }
    >
      {label}
    </NavLink>
  );
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/85 backdrop-blur dark:border-slate-800 dark:bg-slate-950/85">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-600 text-lg font-bold text-white">
              ✂
            </span>
            <span>
              <span className="block text-base font-bold leading-tight">{BRAND.name}</span>
              <span className="hidden text-xs text-slate-500 sm:block dark:text-slate-400">
                {BRAND.tagline}
              </span>
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            {link("/", "Dashboard")}
            {link("/upload", "Upload")}
            <span className="ml-1">
              <ThemeToggle />
            </span>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      <footer className="border-t border-slate-200 py-6 text-center text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
        {BRAND.name} · {BRAND.tagline}
      </footer>
    </div>
  );
}
