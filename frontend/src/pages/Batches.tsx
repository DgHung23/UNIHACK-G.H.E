/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { PackageSearch, Plus, Search, Thermometer } from "lucide-react";
import { api, STATUS_LABEL } from "../api/client";
import { useAuth } from "../auth";
import { Card, Empty, ErrorBox, Freshness, FruitTag, Journey, PageTitle, RulBar, Severity, Spinner, StatusBadge } from "../components/ui";

export default function Batches() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [status, setStatus] = useState("");
  const [fruitId, setFruit] = useState("");
  useEffect(() => { setQ(params.get("q") || ""); }, [params]);
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (status) p.set("status", status);
  if (fruitId) p.set("fruitId", fruitId);
  const batches = useQuery<any[]>({ queryKey: ["batches", q, status, fruitId], queryFn: () => api(`/batches?${p}`) });
  const shelf = Object.fromEntries((fruits.data || []).map((f) => [f.fruitId, f.shelfRefDays]));
  const rows = batches.data || [];

  return (
    <div>
      <PageTitle eyebrow="Truy xuất" sub={`${rows.length} lô${status || fruitId || q ? " khớp bộ lọc" : " trong hệ thống"}`}
        actions={(user?.role === "FARMER" || user?.role === "ADMIN") && <Link to="/batches/new" className="btn-primary"><Plus size={16} />Tạo lô mới</Link>}>
        Lô hàng
      </PageTitle>
      <Card bodyClass="p-0">
        <div className="grid gap-2 border-b border-line p-4 sm:grid-cols-[1fr_200px_200px]">
          <label className="relative">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-400" />
            <input id="batch-search" className="input pl-9" placeholder="Tìm mã lô, sản phẩm, nông hộ, bên đang giữ…" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
          <select id="batch-status" className="input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Mọi trạng thái</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select id="batch-fruit" className="input" value={fruitId} onChange={(e) => setFruit(e.target.value)}>
            <option value="">Mọi loại quả</option>
            {(fruits.data || []).map((f) => <option key={f.fruitId} value={f.fruitId}>{f.nameVi}</option>)}
          </select>
        </div>
        {batches.isLoading ? <Spinner /> : batches.error ? <div className="p-4"><ErrorBox error={batches.error} /></div> : !rows.length ? (
          <Empty icon={<PackageSearch size={20} />} title="Không có lô nào khớp">Thử bỏ bớt bộ lọc hoặc tìm theo mã lô dạng FC-2026-…</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="border-b border-line bg-paper/60"><th className="th">Lô</th><th className="th">Sản phẩm</th><th className="th">Trạng thái</th><th className="th">Bên đang giữ</th><th className="th">RUL hiện tại</th><th className="th">Độ tươi</th><th className="th">Cảnh báo</th></tr></thead>
              <tbody>
                {rows.map((b) => (
                  <tr key={b.batchId} className="border-b border-line last:border-0 hover:bg-paper/60">
                    <td className="td">
                      <Link className="font-mono text-[13px] font-semibold text-cold-700 hover:underline" to={`/batches/${b.batchId}`}>{b.batchId}</Link>
                      <div className="mt-1.5"><Journey status={b.status} compact /></div>
                    </td>
                    <td className="td"><FruitTag fruitId={b.fruitId} name={b.productName} sub={`${b.variety} · ${b.quantityKg} kg`} /></td>
                    <td className="td"><StatusBadge value={b.status} /></td>
                    <td className="td max-w-[240px]"><div className="truncate">{b.currentActorName}</div><div className="truncate text-xs text-ink-400">từ {b.farmName}</div></td>
                    <td className="td"><RulBar rul={b.latestRul?.rulDaysAtCurrent} freshness={b.latestRul?.freshness} max={shelf[b.fruitId] || 14} /></td>
                    <td className="td"><Freshness value={b.latestRul?.freshness} /></td>
                    <td className="td">
                      <div className="flex flex-wrap gap-1">
                        {b.hasViolation && <span className="chip bg-danger-50 text-danger-600"><Thermometer size={12} />Sự cố nhiệt</span>}
                        {b.openAlertsBySeverity?.HIGH > 0 && !b.hasViolation && <Severity value="HIGH" />}
                        {b.openAlertsBySeverity?.MEDIUM > 0 && <Severity value="MEDIUM" />}
                        {!b.openAlerts && <span className="text-ink-300">—</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
