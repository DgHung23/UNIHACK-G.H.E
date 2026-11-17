/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState, type ReactNode } from "react";
import { fetchBlobUrl, FRESH_COLORS, FRESH_LABEL, STATUS_LABEL } from "../api/client";

export function Card({ title, children, actions, className = "" }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <h2 className="font-semibold text-slate-800">{title}</h2>
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function PageTitle({ children, sub, actions }: { children: ReactNode; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">{children}</h1>
        {sub && <p className="text-sm text-slate-500">{sub}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Freshness({ value }: { value?: string | null }) {
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold text-white" style={{ background: FRESH_COLORS[value] || "#64748b" }}>
      {FRESH_LABEL[value] || value}
    </span>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const cls = value === "SOLD" ? "bg-slate-200 text-slate-700" : value === "IN_TRANSIT" ? "bg-blue-100 text-blue-800" : "bg-emerald-100 text-emerald-800";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{STATUS_LABEL[value] || value}</span>;
}

export function Severity({ value }: { value: string }) {
  const cls = value === "HIGH" ? "bg-red-100 text-red-700" : value === "MEDIUM" ? "bg-amber-100 text-amber-800" : "bg-slate-100 text-slate-700";
  return <span className={`rounded px-1.5 py-0.5 text-xs font-bold ${cls}`}>{value}</span>;
}

export function RulBar({ rul, freshness, max = 14 }: { rul?: number | null; freshness?: string | null; max?: number }) {
  if (rul == null) return <span className="text-slate-400">—</span>;
  const pct = Math.max(3, Math.min(100, (rul / max) * 100));
  return (
    <div className="min-w-[120px]">
      <div className="flex justify-between text-xs"><span className="font-semibold">{rul.toFixed(2)} ngày</span></div>
      <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full" style={{ width: `${pct}%`, background: FRESH_COLORS[freshness || ""] || "#64748b" }} /></div>
    </div>
  );
}

export function Spinner({ label = "Đang tải…" }: { label?: string }) {
  return <div className="flex items-center gap-2 p-4 text-sm text-slate-500"><span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />{label}</div>;
}

export function ErrorBox({ error }: { error: any }) {
  if (!error) return null;
  return <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{String(error.message || error)}</div>;
}

export function Stat({ label, value, tone = "slate", hint }: { label: string; value: ReactNode; tone?: "slate" | "red" | "amber" | "green"; hint?: ReactNode }) {
  const color = { slate: "text-slate-900", red: "text-red-600", amber: "text-amber-600", green: "text-emerald-600" }[tone];
  return (
    <div className="card p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-3xl font-bold ${color}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function AuthImage({ path, alt, className }: { path: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    fetchBlobUrl(path).then((u) => { url = u; setSrc(u); }).catch((e) => setErr(String(e.message || e)));
    return () => { if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (err) return <div className="flex h-40 items-center justify-center rounded bg-slate-100 text-xs text-slate-500">Không tải được ảnh</div>;
  if (!src) return <div className="h-40 animate-pulse rounded bg-slate-100" />;
  return <img src={src} alt={alt} className={className} />;
}

export function Hash({ value, n = 10 }: { value?: string | null; n?: number }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <button title={value} className="mono text-left text-slate-600 hover:text-brand-700"
      onClick={() => { navigator.clipboard?.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1000); }}>
      {copied ? "Đã chép ✓" : `${value.slice(0, n)}…${value.slice(-4)}`}
    </button>
  );
}
