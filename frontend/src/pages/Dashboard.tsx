/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, Bell, Blocks, Camera, Handshake, Package, ShoppingBag, Sprout, Thermometer } from "lucide-react";
import { ago, api, EVENT_LABEL, FRESH_COLORS, FRESH_LABEL, FRUIT_COLOR } from "../api/client";
import { Card, ErrorBox, Freshness, FruitTag, Journey, PageTitle, RulBar, Severity, Spinner, Stat } from "../components/ui";
import FleetMap from "../components/FleetMap";

export const EVENT_ICON: Record<string, any> = { HARVEST: Sprout, HANDOFF: Handshake, VIOLATION: Thermometer, SOLD: ShoppingBag, INSPECTION: Camera };
export const EVENT_TONE: Record<string, string> = {
  HARVEST: "bg-leaf-50 text-leaf-600", HANDOFF: "bg-cold-50 text-cold-600", VIOLATION: "bg-danger-50 text-danger-600",
  SOLD: "bg-ink-900/5 text-ink-600", INSPECTION: "bg-proof-50 text-proof-600",
};

export default function Dashboard() {
  const batches = useQuery<any[]>({ queryKey: ["batches"], queryFn: () => api("/batches") });
  const alerts = useQuery<any[]>({ queryKey: ["alerts"], queryFn: () => api("/alerts") });
  const ledger = useQuery<any>({ queryKey: ["ledger", "", ""], queryFn: () => api("/ledger/events") });
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  if (batches.isLoading) return <Spinner />;
  if (batches.error) return <ErrorBox error={batches.error} />;
  const bs = batches.data || [];
  const shelf = Object.fromEntries((fruits.data || []).map((f) => [f.fruitId, f.shelfRefDays]));
  const active = bs.filter((b) => b.status !== "SOLD");
  const open = (alerts.data || []).filter((a) => !a.acknowledged);
  const violations = open.filter((a) => a.type === "COLD_CHAIN_VIOLATION").length;
  const expiring = [...active].sort((a, b) => (a.latestRul?.rulDaysAtCurrent ?? 99) - (b.latestRul?.rulDaysAtCurrent ?? 99));
  const dist = ["FRESH", "GOOD", "NEAR_EXPIRY", "EXPIRED"].map((f) => ({ key: f, n: active.filter((b) => b.latestRul?.freshness === f).length }));
  const totalKg = active.reduce((s, b) => s + (b.quantityKg || 0), 0);
  const fruitCount: Record<string, number> = {};
  for (const b of active) fruitCount[b.fruitId] = (fruitCount[b.fruitId] || 0) + 1;
  const byFruit = Object.entries(fruitCount).sort((a, b) => b[1] - a[1]);
  const names = Object.fromEntries(bs.map((b) => [b.fruitId, b.productName]));
  const recent = (ledger.data?.events || []).slice(0, 5);
  const today = new Date().toLocaleDateString("vi-VN", { weekday: "long", day: "2-digit", month: "2-digit", year: "numeric" });

  return (
    <div className="space-y-6">
      <PageTitle eyebrow={today} sub="Tình trạng các lô trái cây đang lưu thông và bằng chứng đã ghi trên sổ cái">Tổng quan chuỗi lạnh</PageTitle>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={<Package size={19} />} label="Lô đang lưu thông" value={active.length} hint={`${totalKg.toLocaleString("vi-VN")} kg · ${bs.length - active.length} lô đã bán`} />
        <Stat icon={<Bell size={19} />} label="Cảnh báo chưa xử lý" value={open.length} tone={open.length ? "amber" : "green"} hint={<Link to="/alerts" className="text-cold-600 hover:underline">Xem cảnh báo</Link>} />
        <Stat icon={<Thermometer size={19} />} label="Sự cố chuỗi lạnh" value={violations} tone={violations ? "red" : "green"} hint="nhiệt độ vượt ngưỡng ≥ 2 giờ" />
        <Stat icon={<Blocks size={19} />} label="Sự kiện đã khoá trên sổ cái" value={ledger.data?.count ?? "…"} tone="proof" hint={ledger.data?.mode === "mock" ? "sổ cái mô phỏng" : "trên blockchain"} />
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card title="Vị trí các lô đang lưu thông" subtitle="Màu theo loại quả · viền đỏ: có sự cố nhiệt độ" className="xl:col-span-2" bodyClass="p-3">
          <FleetMap batches={active} height={380} />
          <div className="flex flex-wrap gap-x-4 gap-y-1 px-2 pt-3 text-xs text-ink-600">
            {byFruit.map(([f, n]) => (
              <span key={f} className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: FRUIT_COLOR[f] }} />{names[f]} <span className="tnum text-ink-400">{n}</span></span>
            ))}
          </div>
        </Card>
        <div className="flex flex-col gap-6">
          <Card title="Độ tươi hàng đang lưu thông">
            <div className="flex h-3 overflow-hidden rounded-full bg-ink-900/5">
              {dist.filter((d) => d.n).map((d) => <div key={d.key} style={{ width: `${(d.n / Math.max(1, active.length)) * 100}%`, background: FRESH_COLORS[d.key] }} />)}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {dist.map((d) => (
                <div key={d.key} className="flex items-center justify-between rounded-lg bg-paper px-3 py-2">
                  <span className="inline-flex items-center gap-2 text-sm"><span className="h-2 w-2 rounded-full" style={{ background: FRESH_COLORS[d.key] }} />{FRESH_LABEL[d.key]}</span>
                  <span className="tnum font-display font-semibold">{d.n}</span>
                </div>
              ))}
            </div>
          </Card>
          <Card title="Hoạt động sổ cái" subtitle="Sự kiện mới nhất" bodyClass="p-2" actions={<Link to="/ledger" className="inline-flex items-center gap-1 text-xs font-semibold text-cold-600">Tất cả <ArrowRight size={13} /></Link>}>
            <ul className="divide-y divide-line">
              {recent.map((e: any) => {
                const Icon = EVENT_ICON[e.type] || Blocks;
                return (
                  <li key={e.eventId}>
                    <Link to={`/batches/${e.batchId}`} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-paper">
                      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${EVENT_TONE[e.type]}`}><Icon size={15} /></span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{EVENT_LABEL[e.type]} · <span className="font-mono text-xs text-ink-600">{e.batchId}</span></span>
                        <span className="tnum block text-xs text-ink-400">khối #{e.blockNumber} · {ago(e.ts)}</span>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </Card>
        </div>
      </div>

      <Card title="Ưu tiên bán trước" subtitle="Lô đang lưu thông, xếp theo số ngày còn dùng được (RUL) tăng dần" bodyClass="p-0"
        actions={<Link to="/batches" className="btn-secondary">Tất cả lô <ArrowRight size={14} /></Link>}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead><tr className="border-b border-line bg-paper/60"><th className="th">Lô</th><th className="th">Sản phẩm</th><th className="th">Hành trình</th><th className="th">Đang ở</th><th className="th">RUL</th><th className="th">Độ tươi</th><th className="th">Cảnh báo</th></tr></thead>
            <tbody>
              {expiring.slice(0, 8).map((b) => (
                <tr key={b.batchId} className="border-b border-line last:border-0 hover:bg-paper/60">
                  <td className="td"><Link className="font-mono text-[13px] font-semibold text-cold-700 hover:underline" to={`/batches/${b.batchId}`}>{b.batchId}</Link></td>
                  <td className="td"><FruitTag fruitId={b.fruitId} name={b.productName} sub={`${b.quantityKg} kg · ${b.originProvince}`} /></td>
                  <td className="td"><Journey status={b.status} compact /></td>
                  <td className="td max-w-[220px] truncate text-ink-600">{b.currentActorName}</td>
                  <td className="td"><RulBar rul={b.latestRul?.rulDaysAtCurrent} freshness={b.latestRul?.freshness} max={shelf[b.fruitId] || 14} /></td>
                  <td className="td"><Freshness value={b.latestRul?.freshness} /></td>
                  <td className="td">{b.openAlertsBySeverity?.HIGH ? <Severity value="HIGH" /> : b.openAlertsBySeverity?.MEDIUM ? <Severity value="MEDIUM" /> : <span className="text-ink-300">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
