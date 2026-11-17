import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../auth";
import { api, ROLE_LABEL } from "../api/client";

type DemoUser = { username: string; role: string; actorName: string };

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("demo1234");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const users = useQuery<DemoUser[]>({ queryKey: ["demo-users"], queryFn: () => api("/auth/demo-users", { auth: false }) });

  const submit = async (u = username, p = password) => {
    setBusy(true); setErr(null);
    try { await login(u, p); nav("/"); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-white p-4 flex items-center justify-center">
      <div className="grid w-full max-w-4xl gap-6 md:grid-cols-2">
        <div className="card p-6">
          <div className="text-2xl font-bold text-brand-700">🍓 FruitChain</div>
          <p className="mt-1 text-sm text-slate-500">Quản lý vòng đời trái cây · dự đoán RUL · bằng chứng blockchain</p>
          <form className="mt-6 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <div><label className="label">Tên đăng nhập</label><input className="input" value={username} onChange={(e) => setUsername(e.target.value)} /></div>
            <div><label className="label">Mật khẩu</label><input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            {err && <div className="text-sm text-red-600">{err}</div>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? "Đang đăng nhập…" : "Đăng nhập"}</button>
          </form>
        </div>
        <div className="card p-4">
          <div className="mb-2 text-sm font-semibold text-slate-700">Tài khoản demo <span className="font-normal text-slate-500">(mật khẩu: demo1234) — bấm để vào nhanh</span></div>
          <div className="grid gap-1.5 max-h-[420px] overflow-auto">
            {(users.data || []).map((u) => (
              <button key={u.username} onClick={() => { setUsername(u.username); setPassword("demo1234"); submit(u.username, "demo1234"); }}
                className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 text-left text-sm hover:border-brand-500 hover:bg-brand-50">
                <span><span className="font-mono font-semibold">{u.username}</span><span className="block text-xs text-slate-500">{u.actorName}</span></span>
                <span className="rounded bg-slate-100 px-2 py-0.5 text-xs">{ROLE_LABEL[u.role] || u.role}</span>
              </button>
            ))}
            {users.isError && <div className="text-sm text-red-600">Không kết nối được backend (http://127.0.0.1:8000).</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
