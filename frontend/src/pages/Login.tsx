import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Fingerprint, Link2, Loader2, Search, Thermometer } from "lucide-react";
import { useAuth } from "../auth";
import { api, ROLE_LABEL } from "../api/client";
import { Logo } from "../components/ui";

type DemoUser = { username: string; role: string; actorName: string };
const ROLE_ORDER = ["ADMIN", "FARMER", "WAREHOUSE", "TRANSPORT", "DISTRIBUTOR", "RETAILER", "REGULATOR"];

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("demo1234");
  const [filter, setFilter] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const users = useQuery<DemoUser[]>({ queryKey: ["demo-users"], queryFn: () => api("/auth/demo-users", { auth: false }) });

  const groups = useMemo(() => {
    const f = filter.trim().toLowerCase();
    const list = (users.data || []).filter((u) => !f || `${u.username} ${u.actorName} ${ROLE_LABEL[u.role]}`.toLowerCase().includes(f));
    return ROLE_ORDER.map((r) => ({ role: r, users: list.filter((u) => u.role === r) })).filter((g) => g.users.length);
  }, [users.data, filter]);

  const submit = async (u = username, p = password) => {
    setBusy(u); setErr(null);
    try { await login(u, p); nav("/"); } catch (e) { setErr((e as Error).message); } finally { setBusy(null); }
  };

  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <aside className="relative hidden overflow-hidden bg-ink-900 p-12 text-white lg:flex lg:flex-col">
        <Logo light />
        <div className="my-auto max-w-lg">
          <div className="text-xs font-semibold uppercase tracking-[0.14em] text-cold-300">Chuỗi lạnh trái cây · AI · Avalanche</div>
          <h1 className="mt-3 text-[40px] font-semibold leading-[1.1] tracking-tight">Biết lô trái cây còn tươi bao lâu, và chứng minh được không ai sửa lịch sử của nó.</h1>
          <ul className="mt-8 space-y-4 text-[15px] text-ink-300">
            <li className="flex gap-3"><Thermometer className="mt-0.5 shrink-0 text-cold-300" size={20} />Cảm biến đo nhiệt độ, độ ẩm, vị trí mỗi giờ trên suốt hành trình.</li>
            <li className="flex gap-3"><Fingerprint className="mt-0.5 shrink-0 text-cold-300" size={20} />AI ước tính số ngày còn dùng được từ ảnh chụp và lịch sử nhiệt độ.</li>
            <li className="flex gap-3"><Link2 className="mt-0.5 shrink-0 text-cold-300" size={20} />Mỗi lần bàn giao được khoá vân tay lên sổ cái, ai cũng tự kiểm tra được.</li>
          </ul>
        </div>
        <svg className="absolute -bottom-10 -right-10 opacity-[0.12]" width="420" height="260" viewBox="0 0 420 260" aria-hidden>
          {[0, 1, 2, 3].map((i) => (
            <g key={i} transform={`translate(${i * 105} ${i % 2 ? 40 : 90})`}>
              <rect width="80" height="80" rx="14" fill="none" stroke="#a9bcb5" strokeWidth="3" />
              {i < 3 && <line x1="80" y1="40" x2="105" y2={i % 2 ? 90 : -10} stroke="#a9bcb5" strokeWidth="3" />}
            </g>
          ))}
        </svg>
      </aside>

      <main className="flex items-center justify-center bg-paper p-5 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden"><Logo /></div>
          <h2 className="text-2xl font-semibold">Đăng nhập</h2>
          <p className="mt-1 text-sm text-ink-400">Dùng tài khoản của đơn vị bạn trong chuỗi cung ứng.</p>
          <form className="mt-6 space-y-4" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <div><label className="label" htmlFor="username">Tên đăng nhập</label><input id="username" className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} /></div>
            <div><label className="label" htmlFor="password">Mật khẩu</label><input id="password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            {err && <div className="rounded-lg bg-danger-50 px-3 py-2 text-sm text-danger-700">{err}</div>}
            <button className="btn-primary w-full py-2.5" disabled={!!busy}>{busy === username ? <Loader2 size={16} className="animate-spin" /> : null}Đăng nhập<ArrowRight size={16} /></button>
          </form>

          <div className="mt-8">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold">Vào nhanh bằng tài khoản thử nghiệm</span>
              <span className="text-xs text-ink-400">mật khẩu demo1234</span>
            </div>
            <label className="relative block">
              <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
              <input id="user-filter" className="input pl-9" placeholder="Tìm theo đơn vị hoặc vai trò…" value={filter} onChange={(e) => setFilter(e.target.value)} />
            </label>
            <div className="mt-2 max-h-[300px] space-y-3 overflow-auto rounded-xl border border-line bg-white p-2">
              {users.isError && <div className="p-2 text-sm text-danger-600">Không kết nối được máy chủ FruitChain.</div>}
              {groups.map((g) => (
                <div key={g.role}>
                  <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-400">{ROLE_LABEL[g.role]}</div>
                  {g.users.map((u) => (
                    <button disabled={!!busy} key={u.username} onClick={() => { setUsername(u.username); setPassword("demo1234"); submit(u.username, "demo1234"); }}
                      className="flex w-full items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-left hover:bg-cold-50">
                      <span className="min-w-0"><span className="block truncate text-sm font-medium">{u.actorName}</span><span className="block font-mono text-[11px] text-ink-400">{u.username}</span></span>
                      {busy === u.username ? <Loader2 size={14} className="animate-spin text-cold-500" /> : <ArrowRight size={14} className="text-ink-300" />}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
