/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Bell, Blocks, LayoutDashboard, LogOut, Menu, Package, Search, Settings2, Wrench, X } from "lucide-react";
import { useAuth } from "../auth";
import { api, ROLE_LABEL } from "../api/client";
import { Logo } from "./ui";

const NAV = [
  { to: "/", label: "Tổng quan", icon: LayoutDashboard },
  { to: "/batches", label: "Lô hàng", icon: Package },
  { to: "/alerts", label: "Cảnh báo", icon: Bell, badge: true },
  { to: "/ledger", label: "Sổ cái", icon: Blocks },
  { to: "/settings", label: "Model AI", icon: Settings2, admin: true },
  { to: "/admin", label: "Quản trị", icon: Wrench, admin: true },
];

function NetworkPill() {
  const q = useQuery<any>({ queryKey: ["ledger-network"], queryFn: () => api("/ledger/network", { auth: false }), refetchInterval: 30000 });
  const n = q.data;
  const live = n && n.mode !== "mock" && n.ready;
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-white">
        <span className={`relative flex h-2 w-2`}>
          {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-proof-500 opacity-60" />}
          <span className={`relative inline-flex h-2 w-2 rounded-full ${live ? "bg-proof-500" : "bg-warn-500"}`} />
        </span>
        {n ? (n.mode === "mock" ? "Sổ cái mô phỏng" : n.network) : "Đang kết nối…"}
      </div>
      <div className="mt-1 text-[11px] leading-snug text-ink-300">
        {n ? (n.mode === "mock" ? "Chạy offline, chưa ghi lên Avalanche" : n.chainId ? `chain ${n.chainId}${n.ready ? " · đã kết nối hợp đồng" : ""}` : "") : ""}
      </div>
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: () => api("/alerts") });
  const openCount = (alerts.data || []).filter((a: { acknowledged: boolean }) => !a.acknowledged).length;
  const items = NAV.filter((n) => !n.admin || user?.role === "ADMIN");

  const go = (e: React.FormEvent) => {
    e.preventDefault();
    const v = q.trim().toUpperCase();
    if (!v) return;
    nav(/^FC-\d{4}-\d+$/.test(v) ? `/batches/${v}` : `/batches?q=${encodeURIComponent(q.trim())}`);
    setQ(""); setOpen(false);
  };

  const sidebar = (
    <div className="flex h-full flex-col gap-6 p-4">
      <div className="px-1 pt-1"><Logo light /></div>
      <form onSubmit={go} className="relative">
        <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
        <input aria-label="Tìm lô hàng" id="global-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm mã lô, sản phẩm…"
          className="w-full rounded-lg border border-white/10 bg-white/5 py-2 pl-9 pr-3 text-sm text-white placeholder:text-ink-400 focus:border-cold-400 focus:outline-none" />
      </form>
      <nav className="flex flex-col gap-0.5">
        {items.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={() => setOpen(false)}
            className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? "bg-white text-ink-900" : "text-ink-300 hover:bg-white/5 hover:text-white"}`}>
            <n.icon size={17} />
            <span className="flex-1">{n.label}</span>
            {n.badge && openCount > 0 && <span className="tnum rounded-full bg-danger-500 px-1.5 text-[11px] font-bold text-white">{openCount}</span>}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto flex flex-col gap-3">
        <NetworkPill />
        <div className="flex items-center gap-3 rounded-lg px-1">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-cold-600 font-display text-sm font-semibold uppercase text-white">{user?.username?.slice(0, 2)}</span>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-white">{user?.actor?.name || "Quản trị hệ thống"}</div>
            <div className="truncate text-[11px] text-ink-300">{user?.username} · {ROLE_LABEL[user?.role] || user?.role}</div>
          </div>
          <button title="Đăng xuất" className="rounded-md p-1.5 text-ink-300 hover:bg-white/10 hover:text-white" onClick={() => { logout(); nav("/login"); }}><LogOut size={16} /></button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen md:flex">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 bg-ink-900 md:block">{sidebar}</aside>
      <header className="sticky top-0 z-[1000] flex items-center justify-between bg-ink-900 px-4 py-3 md:hidden">
        <Logo light size={26} />
        <button className="rounded-md p-1.5 text-white" aria-label="Mở menu" onClick={() => setOpen(true)}><Menu size={22} /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-[1100] md:hidden">
          <div className="absolute inset-0 bg-ink-950/60" onClick={() => setOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-72 bg-ink-900">
            <button className="absolute right-3 top-4 rounded-md p-1 text-ink-300" aria-label="Đóng menu" onClick={() => setOpen(false)}><X size={20} /></button>
            {sidebar}
          </div>
        </div>
      )}
      <main className="min-w-0 flex-1 px-4 py-6 md:px-8 md:py-8"><div className="mx-auto max-w-[1280px]">{children}</div></main>
    </div>
  );
}
