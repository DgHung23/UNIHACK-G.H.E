/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState, type ReactNode } from "react";
import { AlertTriangle, Check, Copy, Link2, Loader2, ShieldCheck, ShieldAlert } from "lucide-react";
import { fetchBlobUrl, FRESH_COLORS, FRESH_LABEL, FRUIT_COLOR, STAGES, STATUS_LABEL, stageIndex } from "../api/client";

export function Logo({ light = false, size = 28 }: { light?: boolean; size?: number }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="8" fill={light ? "#1d3a31" : "#0d1c17"} />
        <path d="M8.5 21.5c0-6.5 4.6-11.7 13-12.8-1 8.3-6.2 12.8-13 12.8z" fill="#3b98aa" />
        <path d="M8.5 21.5c3.2-3.4 6.4-6 10-8" stroke="#0d1c17" strokeWidth="1.4" fill="none" strokeLinecap="round" />
        <circle cx="22" cy="22" r="3.2" fill="none" stroke="#a9bcb5" strokeWidth="1.8" />
      </svg>
      <span className={`font-display text-[17px] font-semibold tracking-tight ${light ? "text-white" : "text-ink-900"}`}>
        Fruit<span className="text-cold-400">Chain</span>
      </span>
    </span>
  );
}

export function Card({ title, children, actions, className = "", bodyClass = "p-5", subtitle }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string; bodyClass?: string; subtitle?: ReactNode }) {
  return (
    <section className={`card min-w-0 ${className}`}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-ink-900">{title}</h2>
            {subtitle && <p className="text-xs text-ink-400">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function PageTitle({ children, sub, actions, eyebrow }: { children: ReactNode; sub?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-cold-600">{eyebrow}</div>}
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-ink-900">{children}</h1>
        {sub && <p className="mt-1 text-sm text-ink-400">{sub}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Freshness({ value }: { value?: string | null }) {
  if (!value) return <span className="text-ink-300">—</span>;
  const c = FRESH_COLORS[value] || "#64748b";
  return (
    <span className="chip" style={{ background: `${c}1a`, color: c }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: c }} />{FRESH_LABEL[value] || value}
    </span>
  );
}

export function FruitTag({ fruitId, name, sub }: { fruitId: string; name: string; sub?: ReactNode }) {
  const c = FRUIT_COLOR[fruitId] || "#7f988f";
  return (
    <span className="flex min-w-0 items-center gap-2.5">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg font-display text-[13px] font-semibold text-white" style={{ background: c }}>
        {name.slice(0, 1)}
      </span>
      <span className="min-w-0">
        <span className="block truncate font-medium text-ink-900">{name}</span>
        {sub && <span className="block truncate text-xs text-ink-400">{sub}</span>}
      </span>
    </span>
  );
}

const STATUS_TONE: Record<string, string> = {
  HARVESTED: "bg-leaf-50 text-leaf-700", IN_STORAGE: "bg-cold-50 text-cold-700", IN_TRANSIT: "bg-proof-50 text-proof-700",
  AT_DISTRIBUTOR: "bg-cold-50 text-cold-700", IN_STORE: "bg-leaf-50 text-leaf-700", SOLD: "bg-ink-900/5 text-ink-600",
};
export function StatusBadge({ value }: { value: string }) {
  return <span className={`chip ${STATUS_TONE[value] || "bg-ink-900/5 text-ink-600"}`}>{STATUS_LABEL[value] || value}</span>;
}

export function Severity({ value }: { value: string }) {
  const cls = value === "HIGH" ? "bg-danger-50 text-danger-600" : value === "MEDIUM" ? "bg-warn-50 text-warn-700" : "bg-ink-900/5 text-ink-600";
  return <span className={`chip ${cls}`}>{value === "HIGH" ? "Cao" : value === "MEDIUM" ? "Trung bình" : value}</span>;
}

export function RulBar({ rul, freshness, max = 14 }: { rul?: number | null; freshness?: string | null; max?: number }) {
  if (rul == null) return <span className="text-ink-300">—</span>;
  const pct = Math.max(3, Math.min(100, (rul / max) * 100));
  const c = FRESH_COLORS[freshness || ""] || "#7f988f";
  return (
    <div className="min-w-[128px]">
      <div className="tnum font-display text-sm font-semibold text-ink-900">{rul.toFixed(1)} <span className="font-sans text-xs font-normal text-ink-400">ngày</span></div>
      <div className="mt-1 h-1.5 rounded-full bg-ink-900/5"><div className="h-1.5 rounded-full" style={{ width: `${pct}%`, background: c }} /></div>
    </div>
  );
}

/** Thanh hành trình: Thu hoạch → Kho → Vận chuyển → Phân phối → Cửa hàng → Đã bán */
export function Journey({ status, compact = false }: { status: string; compact?: boolean }) {
  const cur = stageIndex(status);
  if (compact) {
    return (
      <div className="flex items-center gap-1" title={STATUS_LABEL[status]}>
        {STAGES.map((s, i) => (
          <span key={s.key} className={`h-1.5 rounded-full ${i <= cur ? (i === cur ? "w-5 bg-cold-500" : "w-3 bg-cold-300") : "w-3 bg-ink-900/10"}`} />
        ))}
      </div>
    );
  }
  return (
    <ol className="flex items-start">
      {STAGES.map((s, i) => {
        const done = i < cur, now = i === cur;
        return (
          <li key={s.key} className="flex min-w-0 flex-1 flex-col items-center text-center">
            <div className="flex w-full items-center">
              <span className={`h-0.5 flex-1 ${i === 0 ? "invisible" : i <= cur ? "bg-cold-400" : "bg-ink-900/10"}`} />
              <span className={`grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 text-[11px] font-bold ${now ? "border-cold-500 bg-cold-500 text-white ring-4 ring-cold-100" : done ? "border-cold-400 bg-white text-cold-600" : "border-ink-900/10 bg-white text-ink-300"}`}>
                {done ? <Check size={14} strokeWidth={3} /> : i + 1}
              </span>
              <span className={`h-0.5 flex-1 ${i === STAGES.length - 1 ? "invisible" : i < cur ? "bg-cold-400" : "bg-ink-900/10"}`} />
            </div>
            <span className={`mt-1.5 truncate px-1 text-[11px] ${now ? "font-semibold text-ink-900" : "text-ink-400"}`}>{s.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function ProofTag({ ok = true, children }: { ok?: boolean; children?: ReactNode }) {
  return ok ? (
    <span className="chip bg-proof-50 text-proof-600"><ShieldCheck size={13} />{children || "Đã khoá trên sổ cái"}</span>
  ) : (
    <span className="chip bg-danger-50 text-danger-600"><ShieldAlert size={13} />{children || "Sai lệch"}</span>
  );
}

export function Spinner({ label = "Đang tải…" }: { label?: string }) {
  return <div className="flex items-center gap-2 p-4 text-sm text-ink-400"><Loader2 size={16} className="animate-spin text-cold-500" />{label}</div>;
}

export function ErrorBox({ error }: { error: any }) {
  if (!error) return null;
  return <div className="flex items-start gap-2 rounded-lg border border-danger-100 bg-danger-50 p-3 text-sm text-danger-700"><AlertTriangle size={16} className="mt-0.5 shrink-0" />{String(error.message || error)}</div>;
}

export function Stat({ label, value, tone = "slate", hint, icon }: { label: string; value: ReactNode; tone?: "slate" | "red" | "amber" | "green" | "proof"; hint?: ReactNode; icon?: ReactNode }) {
  const color = { slate: "text-ink-900", red: "text-danger-600", amber: "text-warn-600", green: "text-leaf-600", proof: "text-proof-600" }[tone];
  const iconBg = { slate: "bg-cold-50 text-cold-600", red: "bg-danger-50 text-danger-600", amber: "bg-warn-50 text-warn-600", green: "bg-leaf-50 text-leaf-600", proof: "bg-proof-50 text-proof-600" }[tone];
  return (
    <div className="card flex items-start gap-3.5 p-4">
      {icon && <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-lg ${iconBg}`}>{icon}</span>}
      <div className="min-w-0">
        <div className="text-xs font-medium text-ink-400">{label}</div>
        <div className={`tnum mt-0.5 font-display text-[26px] font-semibold leading-none ${color}`}>{value}</div>
        {hint && <div className="mt-1.5 text-xs text-ink-400">{hint}</div>}
      </div>
    </div>
  );
}

export function AuthImage({ path, alt, className }: { path: string; alt: string; className?: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    let url: string | null = null;
    setSrc(null); setErr(null);
    fetchBlobUrl(path).then((u) => {
      if (!active) { URL.revokeObjectURL(u); return; }
      url = u; setSrc(u);
    }).catch((e) => { if (active) setErr(String(e.message || e)); });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [path]);
  if (err) return <div className="flex h-40 items-center justify-center rounded-lg bg-paper text-xs text-ink-400">Không tải được ảnh</div>;
  if (!src) return <div className="h-40 animate-pulse rounded-lg bg-paper" />;
  return <img src={src} alt={alt} className={className} />;
}

export function Hash({ value, n = 10, tone = "proof" }: { value?: string | null; n?: number; tone?: "proof" | "plain" | "bad" }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="text-ink-300">—</span>;
  const cls = tone === "bad" ? "bg-danger-50 text-danger-600" : tone === "plain" ? "bg-ink-900/5 text-ink-600" : "bg-proof-50 text-proof-600";
  return (
    <button title={`${value} — bấm để sao chép`} className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono text-[11.5px] ${cls} hover:brightness-95`}
      onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(value).catch(() => {}); setCopied(true); setTimeout(() => setCopied(false), 1000); }}>
      {copied ? <><Check size={11} />đã chép</> : <>{value.slice(0, n)}…{value.slice(-4)}<Copy size={10} className="opacity-50" /></>}
    </button>
  );
}

export function ChainLink({ ok }: { ok: boolean }) {
  return ok
    ? <span className="inline-flex items-center gap-1 text-xs font-medium text-proof-600"><Link2 size={13} />nối đúng</span>
    : <span className="inline-flex items-center gap-1 text-xs font-semibold text-danger-600"><Link2 size={13} />đứt chuỗi</span>;
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      {icon && <span className="grid h-11 w-11 place-items-center rounded-full bg-paper text-ink-400">{icon}</span>}
      <div className="font-medium text-ink-800">{title}</div>
      {children && <div className="max-w-sm text-sm text-ink-400">{children}</div>}
    </div>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: { key: string; label: string; icon?: ReactNode }[]; value: string; onChange: (k: string) => void }) {
  return (
    <div role="tablist" aria-label="Thông tin lô hàng" className="mb-5 flex gap-1 overflow-x-auto rounded-xl border border-line bg-white p-1 shadow-card">
      {tabs.map((t) => (
        <button role="tab" aria-selected={value === t.key} key={t.key} onClick={() => onChange(t.key)}
          className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition ${value === t.key ? "bg-ink-900 text-white" : "text-ink-600 hover:bg-paper"}`}>
          {t.icon}{t.label}
        </button>
      ))}
    </div>
  );
}
