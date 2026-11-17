import { useState, type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth";
import { api, ROLE_LABEL } from "../api/client";

const NAV = [
  { to: "/", label: "Tổng quan", icon: "📊" },
  { to: "/batches", label: "Lô hàng", icon: "📦" },
  { to: "/alerts", label: "Cảnh báo", icon: "🔔", badge: true },
  { to: "/ledger", label: "Sổ cái", icon: "⛓️" },
  { to: "/settings", label: "Cài đặt model", icon: "⚙️", admin: true },
  { to: "/admin", label: "Quản trị", icon: "🛠️", admin: true },
];

export default function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: () => api("/alerts") });
  const openHigh = (alerts.data || []).filter((a: { acknowledged: boolean }) => !a.acknowledged).length;
  const items = NAV.filter((n) => !n.admin || user?.role === "ADMIN");

  const links = (
    <nav className="flex flex-col gap-1">
      {items.map((n) => (
        <NavLink key={n.to} to={n.to} end={n.to === "/"} onClick={() => setOpen(false)}
          className={({ isActive }) => `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-brand-600 text-white" : "text-slate-700 hover:bg-slate-100"}`}>
          <span>{n.icon}</span><span className="flex-1">{n.label}</span>
          {n.badge && openHigh > 0 && <span className="rounded-full bg-red-500 px-2 text-xs text-white">{openHigh}</span>}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen md:flex">
      <aside className="hidden md:flex w-60 shrink-0 flex-col gap-6 border-r border-slate-200 bg-white p-4 sticky top-0 h-screen">
        <div className="flex items-center gap-2 text-lg font-bold text-brand-700">🍓 FruitChain</div>
        {links}
        <div className="mt-auto rounded-lg bg-slate-50 p-3 text-xs">
          <div className="font-semibold text-slate-800">{user?.username}</div>
          <div className="text-slate-500">{ROLE_LABEL[user?.role] || user?.role}{user?.actor ? ` · ${user.actor.name}` : ""}</div>
          <button className="mt-2 text-red-600 hover:underline" onClick={() => { logout(); nav("/login"); }}>Đăng xuất</button>
        </div>
      </aside>
      <header className="md:hidden sticky top-0 z-[1000] flex items-center justify-between border-b bg-white px-4 py-3">
        <div className="font-bold text-brand-700">🍓 FruitChain</div>
        <button className="btn-secondary" onClick={() => setOpen(!open)}>☰</button>
      </header>
      {open && (
        <div className="md:hidden border-b bg-white p-4 space-y-3 relative z-[999]">
          {links}
          <button className="text-sm text-red-600" onClick={() => { logout(); nav("/login"); }}>Đăng xuất ({user?.username})</button>
        </div>
      )}
      <main className="flex-1 min-w-0 p-4 md:p-6">{children}</main>
    </div>
  );
}
