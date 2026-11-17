/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, FRESH_COLORS, FRESH_LABEL } from "../api/client";
import { Card, ErrorBox, Freshness, PageTitle, RulBar, Severity, Spinner, Stat, StatusBadge } from "../components/ui";

export default function Dashboard() {
  const batches = useQuery<any[]>({ queryKey: ["batches"], queryFn: () => api("/batches") });
  const alerts = useQuery<any[]>({ queryKey: ["alerts"], queryFn: () => api("/alerts") });
  const models = useQuery<any>({ queryKey: ["models"], queryFn: () => api("/meta/models") });
  if (batches.isLoading) return <Spinner />;
  if (batches.error) return <ErrorBox error={batches.error} />;
  const bs = batches.data || [];
  const active = bs.filter((b) => b.status !== "SOLD");
  const open = (alerts.data || []).filter((a) => !a.acknowledged);
  const high = open.filter((a) => a.severity === "HIGH").length;
  const violations = open.filter((a) => a.type === "COLD_CHAIN_VIOLATION").length;
  const expiring = [...active].sort((a, b) => (a.latestRul?.rulDaysAtCurrent ?? 99) - (b.latestRul?.rulDaysAtCurrent ?? 99));
  const dist = ["FRESH", "GOOD", "NEAR_EXPIRY", "EXPIRED"].map((f) => ({ key: f, name: FRESH_LABEL[f], value: active.filter((b) => b.latestRul?.freshness === f).length }));
  const im = models.data?.imageModel;

  return (
    <div className="space-y-5">
      <PageTitle sub="Thời điểm demo: 17/11/2026 13:00 (giờ VN)">Tổng quan</PageTitle>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Tổng số lô" value={bs.length} hint={`${active.length} đang lưu thông`} />
        <Stat label="Cảnh báo HIGH" value={high} tone={high ? "red" : "green"} hint={`${open.length} cảnh báo chưa xử lý`} />
        <Stat label="Vi phạm chuỗi lạnh" value={<span className="inline-flex items-center gap-2">{violations}<span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">🌡️ vi phạm</span></span>} tone={violations ? "red" : "green"} />
        <Stat label="Sắp hết hạn (< 4 ngày)" value={active.filter((b) => (b.latestRul?.rulDaysAtCurrent ?? 99) < 4).length} tone="amber" />
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="Lô sắp hết hạn (RUL tăng dần)" className="lg:col-span-2">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="border-b"><th className="th">Mã lô</th><th className="th">Sản phẩm</th><th className="th">Trạng thái</th><th className="th">RUL hiện tại</th><th className="th">Độ tươi</th><th className="th">Cảnh báo</th></tr></thead>
              <tbody>
                {expiring.map((b) => (
                  <tr key={b.batchId} className="border-b last:border-0 hover:bg-slate-50">
                    <td className="td"><Link className="font-mono font-semibold text-brand-700 hover:underline" to={`/batches/${b.batchId}`}>{b.batchId}</Link></td>
                    <td className="td">{b.productName}</td>
                    <td className="td"><StatusBadge value={b.status} /></td>
                    <td className="td"><RulBar rul={b.latestRul?.rulDaysAtCurrent} freshness={b.latestRul?.freshness} /></td>
                    <td className="td"><Freshness value={b.latestRul?.freshness} /></td>
                    <td className="td">{b.openAlertsBySeverity?.HIGH ? <Severity value="HIGH" /> : b.openAlertsBySeverity?.MEDIUM ? <Severity value="MEDIUM" /> : <span className="text-slate-400">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="space-y-5">
          <Card title="Phân bố độ tươi (lô đang lưu thông)">
            <div className="h-48">
              <ResponsiveContainer>
                <BarChart data={dist}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis allowDecimals={false} width={24} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="value" name="Số lô" radius={[4, 4, 0, 0]}>
                    {dist.map((d) => <Cell key={d.key} fill={FRESH_COLORS[d.key]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Model RUL">
            <div className="space-y-1 text-sm">
              <div>Cảm biến: <span className="font-mono">{models.data?.sensorModel?.version}</span></div>
              <div>Ảnh: {im?.model ? <span className="font-mono text-emerald-700">{im.model.version}</span> : <span className="text-slate-500">chưa nạp (dùng Q10)</span>}</div>
              <div>Hợp nhất: <span className="font-mono">{models.data?.fusion}</span> · Sổ cái: <span className="font-mono">{models.data?.ledgerMode}</span></div>
              <Link to="/settings" className="mt-2 inline-block text-brand-700 hover:underline">⚙️ Cài đặt model →</Link>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
