/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, STATUS_LABEL } from "../api/client";
import { useAuth } from "../auth";
import { Card, ErrorBox, PageTitle, RulBar, Severity, Spinner, StatusBadge } from "../components/ui";

export default function Batches() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [fruitId, setFruit] = useState("");
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (status) params.set("status", status);
  if (fruitId) params.set("fruitId", fruitId);
  const batches = useQuery<any[]>({ queryKey: ["batches", q, status, fruitId], queryFn: () => api(`/batches?${params}`) });

  return (
    <div>
      <PageTitle sub="Tất cả lô trái cây trong hệ thống"
        actions={(user?.role === "FARMER" || user?.role === "ADMIN") && <Link to="/batches/new" className="btn-primary">＋ Tạo lô mới</Link>}>
        Lô hàng
      </PageTitle>
      <Card>
        <div className="mb-4 grid gap-2 sm:grid-cols-3">
          <input className="input" placeholder="Tìm mã lô, sản phẩm, bên giữ…" value={q} onChange={(e) => setQ(e.target.value)} />
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Mọi trạng thái</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select className="input" value={fruitId} onChange={(e) => setFruit(e.target.value)}>
            <option value="">Mọi loại quả</option>
            {(fruits.data || []).map((f) => <option key={f.fruitId} value={f.fruitId}>{f.nameVi}</option>)}
          </select>
        </div>
        {batches.isLoading ? <Spinner /> : batches.error ? <ErrorBox error={batches.error} /> : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="border-b"><th className="th">Mã lô</th><th className="th">Loại quả</th><th className="th">Trạng thái</th><th className="th">Bên đang giữ</th><th className="th">RUL</th><th className="th">Cảnh báo</th></tr></thead>
              <tbody>
                {(batches.data || []).map((b) => (
                  <tr key={b.batchId} className="border-b last:border-0 hover:bg-slate-50">
                    <td className="td"><Link className="font-mono font-semibold text-brand-700 hover:underline" to={`/batches/${b.batchId}`}>{b.batchId}</Link></td>
                    <td className="td">{b.productName}<div className="text-xs text-slate-500">{b.quantityKg} kg · {b.originProvince}</div></td>
                    <td className="td"><StatusBadge value={b.status} /></td>
                    <td className="td">{b.currentActorName}</td>
                    <td className="td"><RulBar rul={b.latestRul?.rulDaysAtCurrent} freshness={b.latestRul?.freshness} /></td>
                    <td className="td space-x-1">
                      {b.hasViolation && <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-semibold text-red-700">🌡️ Vi phạm</span>}
                      {b.openAlertsBySeverity?.HIGH > 0 && <Severity value="HIGH" />}
                      {b.openAlertsBySeverity?.MEDIUM > 0 && <Severity value="MEDIUM" />}
                      {!b.openAlerts && <span className="text-slate-400">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!batches.data?.length && <div className="p-6 text-center text-sm text-slate-500">Không có lô nào.</div>}
          </div>
        )}
      </Card>
    </div>
  );
}
