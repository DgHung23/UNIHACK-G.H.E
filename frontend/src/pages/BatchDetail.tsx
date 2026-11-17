/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { api, EVENT_LABEL, fmtTs, ROLE_LABEL } from "../api/client";
import { useAuth } from "../auth";
import { Card, ErrorBox, Freshness, Hash, PageTitle, RulBar, Spinner, StatusBadge } from "../components/ui";
import RulChart from "../components/RulChart";
import RouteMap from "../components/RouteMap";
import VerifyPanel from "../components/VerifyPanel";
import InspectionsPanel from "../components/InspectionsPanel";

const TABS = [["overview", "Tổng quan"], ["rul", "RUL"], ["timeline", "Timeline"], ["map", "Bản đồ"], ["sensors", "Cảm biến"], ["images", "Ảnh kiểm tra"], ["verify", "Kiểm chứng"]] as const;
const EV_DOT: Record<string, string> = { HARVEST: "bg-green-600", HANDOFF: "bg-blue-600", VIOLATION: "bg-red-600", SOLD: "bg-slate-600", INSPECTION: "bg-pink-600" };

export default function BatchDetail() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const [tab, setTab] = useState<string>("overview");
  const batch = useQuery<any>({ queryKey: ["batch", id], queryFn: () => api(`/batches/${id}`) });
  const events = useQuery<any[]>({ queryKey: ["events", id], queryFn: () => api(`/batches/${id}/events`) });
  const rul = useQuery<any[]>({ queryKey: ["rul", id], queryFn: () => api(`/batches/${id}/rul`), enabled: tab === "rul" || tab === "overview" });
  const readings = useQuery<any[]>({ queryKey: ["readings", id], queryFn: () => api(`/batches/${id}/readings`), enabled: tab === "map" || tab === "sensors" });
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  const insp = useQuery<any[]>({ queryKey: ["inspections", id], queryFn: () => api(`/batches/${id}/inspections`), enabled: tab === "rul" });

  if (batch.isLoading) return <Spinner />;
  if (batch.error) return <ErrorBox error={batch.error} />;
  const b = batch.data;
  const fruit = (fruits.data || []).find((f) => f.fruitId === b.fruitId);
  const isHolder = user?.role === "ADMIN" || user?.actorId === b.currentActorId;
  const canUpload = isHolder || user?.role === "REGULATOR";

  return (
    <div>
      <PageTitle sub={<>{b.productName} · {b.variety} · {b.quantityKg} kg · {b.farmName}</>}
        actions={<div className="flex items-center gap-2"><StatusBadge value={b.status} /><Link to={`/trace/${id}`} target="_blank" className="btn-secondary">🔗 Trang truy xuất công khai</Link></div>}>
        <span className="font-mono">{id}</span>
      </PageTitle>
      {b.demoNote && <div className="mb-4 rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">ℹ️ {b.demoNote}</div>}

      <div className="mb-4 flex gap-1 overflow-x-auto border-b">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium ${tab === k ? "border-brand-600 text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}>{l}</button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid gap-5 lg:grid-cols-3">
          <Card title="Thông tin lô" className="lg:col-span-2">
            <dl className="grid gap-3 sm:grid-cols-2 text-sm">
              <Info k="Loại quả">{b.productName}</Info>
              <Info k="Giống">{b.variety}</Info>
              <Info k="Nông hộ">{b.farmName} ({b.originProvince})</Info>
              <Info k="Thu hoạch">{fmtTs(b.harvestTs)}</Info>
              <Info k="Chứng nhận">{(b.certifications || []).join(", ") || "—"}</Info>
              <Info k="Bên đang giữ">{b.currentActorName} <span className="text-slate-500">({ROLE_LABEL[b.currentActorRole] || b.currentActorRole})</span></Info>
              <Info k="RUL hiện tại"><RulBar rul={b.latestRul?.rulDaysAtCurrent} freshness={b.latestRul?.freshness} max={fruit?.shelfRefDays || 14} /></Info>
              <Info k="RUL nếu bảo quản chuẩn">{b.latestRul?.rulDaysAtOptimal?.toFixed(2)} ngày · <Freshness value={b.latestRul?.freshness} /></Info>
              <Info k="metadataHash"><Hash value={b.metadataHash} n={16} /></Info>
              <Info k="Số reading / sự kiện">{b.readingCount} / {b.eventCount}</Info>
            </dl>
          </Card>
          <Card title="QR truy xuất">
            <div className="flex flex-col items-center gap-2">
              <QRCodeSVG value={`${location.origin}/trace/${id}`} size={160} />
              <div className="mono text-center text-slate-500">{location.origin}/trace/{id}</div>
              <div className="text-[11px] text-slate-400">Payload demo: {b.qrPayload}</div>
            </div>
          </Card>
          {isHolder && b.status !== "SOLD" && <Actions b={b} />}
        </div>
      )}

      {tab === "rul" && (
        <Card title="Đường RUL theo thời gian + nhiệt độ">
          {rul.isLoading ? <Spinner /> : <RulChart points={rul.data || []} alertTempC={fruit?.alertTempC} inspections={insp.data || []} />}
          <p className="mt-2 text-xs text-slate-500">Mô hình cảm biến Q10 (baseline). Khoảng tin cậy ±15% là giả định demo. Chấm hồng: RUL dự đoán từ ảnh kiểm tra.</p>
        </Card>
      )}

      {tab === "timeline" && (
        <Card title="Chuỗi sự kiện trên sổ cái">
          {events.isLoading ? <Spinner /> : (
            <ol className="relative ml-3 border-l border-slate-200">
              {(events.data || []).map((e) => (
                <li key={e.eventId} className="mb-5 ml-5">
                  <span className={`absolute -left-[7px] mt-1.5 h-3.5 w-3.5 rounded-full ring-4 ring-white ${EV_DOT[e.type] || "bg-slate-400"}`} />
                  <div className="flex flex-wrap items-baseline gap-x-3">
                    <span className="font-semibold">{EVENT_LABEL[e.type] || e.type}</span>
                    <span className="text-sm text-slate-500">{fmtTs(e.ts)}</span>
                    <span className="font-mono text-xs text-slate-400">{e.eventId}</span>
                    {e.linkOk ? <span className="text-xs text-emerald-600">⛓ liên kết OK</span> : <span className="text-xs font-bold text-red-600">⛓ liên kết lỗi</span>}
                  </div>
                  <div className="text-sm text-slate-700">{e.actorName}{e.toActorName ? ` → ${e.toActorName}` : ""}</div>
                  {e.type === "VIOLATION" && <div className="text-sm text-red-700">Vượt {e.payload.thresholdC}°C trong {e.payload.durationHours} giờ, tối đa {e.payload.maxTempC}°C{e.payload.ongoing ? " (đang tiếp diễn)" : ""}</div>}
                  {e.type === "HANDOFF" && <div className="text-xs text-slate-500">Chặng: {e.payload.legLabel} · {e.payload.readingCount} reading</div>}
                  {e.type === "INSPECTION" && <div className="text-xs text-slate-500">Ảnh {e.payload.imageId} · RUL ảnh {e.payload.rulImageDays ?? "—"} · model {e.payload.modelVersion}</div>}
                  <div className="mt-1 flex flex-wrap gap-x-4 text-xs text-slate-500">
                    <span>RUL: <b>{e.rulSnapshot?.rulDaysAtCurrent ?? "—"}</b> ngày <Freshness value={e.rulSnapshot?.freshness} /></span>
                    <span>block #{e.blockNumber}</span><span>tx <Hash value={e.txHash} n={10} /></span><span>eventHash <Hash value={e.eventHash} n={8} /></span>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      )}

      {tab === "map" && <Card title="Tuyến đường (GPS)">{readings.isLoading || events.isLoading ? <Spinner /> : <RouteMap readings={readings.data || []} events={events.data || []} />}</Card>}
      {tab === "sensors" && <Card title="Dữ liệu cảm biến">{readings.isLoading ? <Spinner /> : <SensorTable rows={readings.data || []} alertTempC={fruit?.alertTempC} />}</Card>}
      {tab === "images" && <Card title="Ảnh kiểm tra"><InspectionsPanel batch={b} canUpload={canUpload} /></Card>}
      {tab === "verify" && <Card title="Kiểm chứng toàn vẹn"><VerifyPanel batchId={id} /></Card>}
    </div>
  );
}

function Info({ k, children }: { k: string; children: React.ReactNode }) {
  return <div><dt className="label">{k}</dt><dd>{children}</dd></div>;
}

function Actions({ b }: { b: any }) {
  const qc = useQueryClient();
  const actors = useQuery<any[]>({ queryKey: ["actors"], queryFn: () => api("/meta/actors") });
  const [to, setTo] = useState("");
  const done = () => ["batch", "events", "batches", "rul"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const handoff = useMutation({ mutationFn: () => api(`/batches/${b.batchId}/handoff`, { body: { toActorId: to } }), onSuccess: done });
  const sold = useMutation({ mutationFn: () => api(`/batches/${b.batchId}/sold`, { body: {} }), onSuccess: done });
  const opts = (actors.data || []).filter((a) => a.actorId !== b.currentActorId && a.role !== "REGULATOR" && a.role !== "FARMER");
  return (
    <Card title="Thao tác" className="lg:col-span-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[260px] flex-1"><label className="label">Chuyển giao cho</label>
          <select className="input" value={to} onChange={(e) => setTo(e.target.value)}>
            <option value="">— chọn bên nhận —</option>
            {opts.map((a) => <option key={a.actorId} value={a.actorId}>{a.name} ({ROLE_LABEL[a.role]})</option>)}
          </select>
        </div>
        <button className="btn-primary" disabled={!to || handoff.isPending} onClick={() => handoff.mutate()}>🤝 Chuyển giao (ghi HANDOFF)</button>
        {b.currentActorRole === "RETAILER" && <button className="btn-secondary" disabled={sold.isPending} onClick={() => { if (confirm("Xác nhận đã bán lô này? Sau khi bán không ghi thêm sự kiện được.")) sold.mutate(); }}>💰 Đánh dấu đã bán</button>}
      </div>
      <div className="mt-3"><ErrorBox error={handoff.error || sold.error} /></div>
      {handoff.data && <div className="mt-2 text-sm text-emerald-700">✔ Đã ghi {(handoff.data as any).event.eventId} (block #{(handoff.data as any).event.blockNumber})</div>}
    </Card>
  );
}

function SensorTable({ rows, alertTempC }: { rows: any[]; alertTempC?: number }) {
  const [onlyHot, setOnlyHot] = useState(false);
  const shown = [...rows].reverse().filter((r) => !onlyHot || (alertTempC != null && r.tempC > alertTempC));
  return (
    <div>
      <label className="mb-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyHot} onChange={(e) => setOnlyHot(e.target.checked)} /> Chỉ hiện reading vượt ngưỡng {alertTempC}°C</label>
      <div className="max-h-[520px] overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-white"><tr className="border-b"><th className="th">Thời điểm</th><th className="th">Nhiệt độ</th><th className="th">Độ ẩm</th><th className="th">Ethylene</th><th className="th">Vị trí</th><th className="th">Thiết bị</th><th className="th">Chữ ký</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.ts} className={`border-b ${alertTempC != null && r.tempC > alertTempC ? "bg-red-50" : ""}`}>
                <td className="td whitespace-nowrap">{fmtTs(r.ts)}</td><td className="td">{r.tempC.toFixed(1)}°C</td><td className="td">{r.humidityPct}%</td>
                <td className="td">{r.ethylenePpm.toFixed(1)} ppm</td><td className="td font-mono text-xs">{r.lat.toFixed(4)}, {r.lon.toFixed(4)}</td>
                <td className="td font-mono text-xs">{r.deviceId}</td><td className="td"><Hash value={r.deviceSig} n={8} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
