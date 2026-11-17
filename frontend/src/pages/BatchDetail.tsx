/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QRCodeSVG } from "qrcode.react";
import { ArrowLeft, Blocks, Camera, ExternalLink, Handshake, LineChart, Map as MapIcon, Radio, ShoppingBag, Thermometer, Waves } from "lucide-react";
import { api, EVENT_LABEL, fmtShort, fmtTs, FRUIT_COLOR, ROLE_LABEL } from "../api/client";
import { useAuth } from "../auth";
import { Card, ChainLink, ErrorBox, Freshness, Hash, Journey, Spinner, StatusBadge, Tabs } from "../components/ui";
import RulChart from "../components/RulChart";
import RouteMap from "../components/RouteMap";
import InspectionsPanel from "../components/InspectionsPanel";
import { EVENT_ICON, EVENT_TONE } from "./Dashboard";

const TABS = [
  { key: "overview", label: "Tổng quan", icon: <Waves size={15} /> },
  { key: "timeline", label: "Sổ cái", icon: <Blocks size={15} /> },
  { key: "rul", label: "Hạn dùng (RUL)", icon: <LineChart size={15} /> },
  { key: "map", label: "Bản đồ", icon: <MapIcon size={15} /> },
  { key: "sensors", label: "Cảm biến", icon: <Radio size={15} /> },
  { key: "images", label: "Ảnh kiểm tra", icon: <Camera size={15} /> },
];

export default function BatchDetail() {
  const { id = "" } = useParams();
  const { user } = useAuth();
  const [tab, setTab] = useState<string>("overview");
  const batch = useQuery<any>({ queryKey: ["batch", id], queryFn: () => api(`/batches/${id}`) });
  const events = useQuery<any[]>({ queryKey: ["events", id], queryFn: () => api(`/batches/${id}/events`) });
  const rul = useQuery<any[]>({ queryKey: ["rul", id], queryFn: () => api(`/batches/${id}/rul`), enabled: tab === "rul" || tab === "overview" });
  const readings = useQuery<any[]>({ queryKey: ["readings", id], queryFn: () => api(`/batches/${id}/readings`), enabled: tab === "map" || tab === "sensors" });
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  const insp = useQuery<any[]>({ queryKey: ["inspections", id], queryFn: () => api(`/batches/${id}/inspections`), enabled: tab === "rul" || tab === "overview" });

  if (batch.isLoading) return <Spinner />;
  if (batch.error) return <ErrorBox error={batch.error} />;
  const b = batch.data;
  const fruit = (fruits.data || []).find((f) => f.fruitId === b.fruitId);
  const isHolder = user?.role === "ADMIN" || user?.actorId === b.currentActorId;
  const canUpload = isHolder || user?.role === "REGULATOR";
  const lr = b.latestRul || {};
  const color = FRUIT_COLOR[b.fruitId] || "#3b98aa";
  const lastInsp = (insp.data || [])[0];
  const violations = (events.data || []).filter((e) => e.type === "VIOLATION");

  return (
    <div>
      <Link to="/batches" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-400 hover:text-ink-900"><ArrowLeft size={15} />Lô hàng</Link>

      <section className="relative mb-5 overflow-hidden rounded-2xl bg-ink-900 text-white shadow-lift">
        <div className="absolute inset-y-0 right-0 w-1/2 opacity-[0.18]" style={{ background: `radial-gradient(circle at 80% 30%, ${color}, transparent 60%)` }} />
        <div className="relative flex flex-wrap items-start justify-between gap-4 p-6">
          <div className="flex min-w-0 items-start gap-4">
            <span className="grid h-14 w-14 shrink-0 place-items-center rounded-xl font-display text-2xl font-semibold" style={{ background: color }}>{b.productName.slice(0, 1)}</span>
            <div className="min-w-0">
              <div className="font-mono text-sm text-ink-300">{id}</div>
              <h1 className="text-2xl font-semibold leading-tight">{b.productName} <span className="font-sans text-base font-normal text-ink-300">· {b.variety}</span></h1>
              <div className="mt-1 text-sm text-ink-300">{b.quantityKg.toLocaleString("vi-VN")} kg · {b.farmName}, {b.originProvince} · hái {fmtShort(b.harvestTs)}</div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <StatusBadge value={b.status} />
                {(b.certifications || []).map((c: string) => <span key={c} className="chip bg-white/10 text-white">{c}</span>)}
                {b.hasViolation && <span className="chip bg-danger-500 text-white"><Thermometer size={12} />Có sự cố nhiệt độ</span>}
              </div>
            </div>
          </div>
          <Link to={`/trace/${id}`} target="_blank" className="btn border border-white/20 bg-white/10 text-white hover:bg-white/20"><ExternalLink size={15} />Trang truy xuất công khai</Link>
        </div>
        <div className="relative grid grid-cols-2 gap-px border-t border-white/10 bg-white/10 md:grid-cols-4">
          <HeroStat label="Còn dùng được (hiện tại)" value={lr.rulDaysAtCurrent?.toFixed(1)} unit="ngày" extra={<Freshness value={lr.freshness} />} />
          <HeroStat label="Nếu bảo quản đúng chuẩn" value={lr.rulDaysAtOptimal?.toFixed(1)} unit="ngày" />
          <HeroStat label="Nhiệt độ gần nhất" value={lr.tempC?.toFixed(1)} unit="°C" extra={fruit && <span className="text-[11px] text-ink-300">chuẩn {fruit.optimalTempMinC}–{fruit.optimalTempMaxC}°C</span>} />
          <HeroStat label="Sự kiện trên sổ cái" value={b.eventCount} unit="mốc" extra={<span className="text-[11px] text-ink-300">{b.readingCount} lần đo</span>} />
        </div>
      </section>

      <Card className="mb-5" bodyClass="px-4 py-5"><Journey status={b.status} /></Card>

      <Tabs tabs={TABS} value={tab} onChange={setTab} />

      {tab === "overview" && (
        <div className="grid gap-5 xl:grid-cols-3">
          <div className="flex flex-col gap-5 xl:col-span-2">
            <Card title="Hạn dùng theo thời gian" subtitle="RUL tính từ nhiệt độ thực tế từng giờ" actions={<button className="text-xs font-semibold text-cold-600" onClick={() => setTab("rul")}>Chi tiết</button>}>
              {rul.isLoading ? <Spinner /> : <RulChart points={rul.data || []} alertTempC={fruit?.alertTempC} inspections={insp.data || []} height={260} />}
            </Card>
            <Card title="Bàn giao gần đây" bodyClass="p-2" actions={<button className="text-xs font-semibold text-cold-600" onClick={() => setTab("timeline")}>Xem sổ cái</button>}>
              <ul className="divide-y divide-line">
                {(events.data || []).slice(-5).reverse().map((e) => <EventRow key={e.eventId} e={e} />)}
              </ul>
            </Card>
          </div>
          <div className="flex flex-col gap-5">
            <Card title="Bên đang giữ lô">
              <div className="font-medium">{b.currentActorName}</div>
              <div className="text-sm text-ink-400">{ROLE_LABEL[b.currentActorRole] || b.currentActorRole}</div>
              {violations.length > 0 && (
                <div className="mt-3 rounded-lg bg-danger-50 p-3 text-sm text-danger-700">
                  {violations.map((v) => <div key={v.eventId}>Vượt {v.payload.thresholdC}°C trong {v.payload.durationHours} giờ (tối đa {v.payload.maxTempC}°C) khi ở <b>{v.actorName}</b>{v.payload.ongoing ? ", đang tiếp diễn" : ""}.</div>)}
                </div>
              )}
              {lastInsp && <div className="mt-3 rounded-lg bg-proof-50 p-3 text-sm text-proof-700">Kiểm tra ảnh {fmtShort(lastInsp.ts)}: AI ước tính còn <b>{lastInsp.rulImage ?? "—"} ngày</b>.</div>}
            </Card>
            <Card title="Mã QR truy xuất" subtitle="In lên thùng hàng để người mua quét">
              <div className="flex flex-col items-center gap-3">
                <div className="rounded-xl border border-line p-3"><QRCodeSVG value={`${location.origin}/trace/${id}`} size={150} fgColor="#0d1c17" /></div>
                <div className="mono text-center text-ink-400">{location.origin}/trace/{id}</div>
              </div>
            </Card>
            <Card title="Dấu vân tay thông tin lô">
              <p className="mb-2 text-xs text-ink-400">SHA-256 của thông tin lúc thu hoạch, ghi ở khối đầu tiên của lô.</p>
              <Hash value={b.metadataHash} n={18} />
            </Card>
            {isHolder && b.status !== "SOLD" && <Actions b={b} />}
          </div>
        </div>
      )}

      {tab === "timeline" && (
        <Card title="Chuỗi sự kiện của lô" subtitle="Mỗi sự kiện liên kết với hash của sự kiện trước trong cùng lô">
          {events.isLoading ? <Spinner /> : <BlockChain events={events.data || []} />}
        </Card>
      )}
      {tab === "rul" && (
        <Card title="Đường hạn dùng (RUL) và nhiệt độ" subtitle="Mô hình cảm biến Q10 · vùng mờ ±15% · chấm tím: RUL do AI ước tính từ ảnh">
          {rul.isLoading ? <Spinner /> : <RulChart points={rul.data || []} alertTempC={fruit?.alertTempC} inspections={insp.data || []} height={380} />}
        </Card>
      )}
      {tab === "map" && <Card title="Tuyến đường GPS" bodyClass="p-3">{readings.isLoading || events.isLoading ? <Spinner /> : <RouteMap readings={readings.data || []} events={events.data || []} />}</Card>}
      {tab === "sensors" && <Card title="Dữ liệu cảm biến" subtitle="Mỗi lần đo được thiết bị ký bằng khoá riêng" bodyClass="p-0">{readings.isLoading ? <Spinner /> : <SensorTable rows={readings.data || []} alertTempC={fruit?.alertTempC} />}</Card>}
      {tab === "images" && <Card title="Ảnh kiểm tra"><InspectionsPanel batch={b} canUpload={canUpload} /></Card>}
    </div>
  );
}

function HeroStat({ label, value, unit, extra }: { label: string; value: any; unit: string; extra?: React.ReactNode }) {
  return (
    <div className="bg-ink-900 px-6 py-4">
      <div className="text-[11px] font-medium uppercase tracking-[0.08em] text-ink-300">{label}</div>
      <div className="tnum mt-1 font-display text-2xl font-semibold">{value ?? "—"} <span className="font-sans text-sm font-normal text-ink-300">{unit}</span></div>
      {extra && <div className="mt-1">{extra}</div>}
    </div>
  );
}

function EventRow({ e }: { e: any }) {
  const Icon = EVENT_ICON[e.type] || Blocks;
  return (
    <li className="flex items-center gap-3 px-3 py-2.5">
      <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${EVENT_TONE[e.type]}`}><Icon size={15} /></span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{EVENT_LABEL[e.type]}{e.toActorName ? <span className="font-normal text-ink-600"> → {e.toActorName}</span> : e.actorName ? <span className="font-normal text-ink-600"> · {e.actorName}</span> : null}</div>
        <div className="tnum text-xs text-ink-400">{fmtTs(e.ts)} · khối #{e.blockNumber}</div>
      </div>
      <ChainLink ok={e.linkOk} />
    </li>
  );
}

function BlockChain({ events }: { events: any[] }) {
  return (
    <ol className="flex flex-col">
      {events.map((e, i) => {
        const Icon = EVENT_ICON[e.type] || Blocks;
        const p = e.payload || {};
        return (
          <li key={e.eventId}>
            {i > 0 && (
              <div className="ml-[19px] flex items-center gap-2 border-l-2 border-dashed border-proof-100 py-2 pl-5 text-[11px] text-ink-400">
                <span>vân tay trước</span><Hash value={e.prevHash} n={8} tone={e.linkOk ? "proof" : "bad"} /><ChainLink ok={e.linkOk} />
              </div>
            )}
            <div className={`flex gap-4 rounded-xl border p-4 ${e.type === "VIOLATION" ? "border-danger-100 bg-danger-50/40" : "border-line"}`}>
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${EVENT_TONE[e.type]}`}><Icon size={18} /></span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <div className="font-semibold">{EVENT_LABEL[e.type]} <span className="font-mono text-xs font-normal text-ink-400">{e.eventId}</span></div>
                  <div className="tnum font-mono text-xs text-ink-400">khối #{e.blockNumber}</div>
                </div>
                <div className="text-sm text-ink-600">{fmtTs(e.ts)} · {e.actorName}{e.toActorName ? ` → ${e.toActorName}` : ""}</div>
                {e.type === "VIOLATION" && <div className="mt-1 text-sm font-medium text-danger-700">Vượt {p.thresholdC}°C trong {p.durationHours} giờ, cao nhất {p.maxTempC}°C{p.ongoing ? " · đang tiếp diễn" : ""}</div>}
                {e.type === "HANDOFF" && <div className="mt-1 text-xs text-ink-400">Khoá {p.readingCount} lần đo của chặng {p.legLabel}</div>}
                {e.type === "INSPECTION" && <div className="mt-1 text-xs text-ink-400">Ảnh {p.imageId} · AI ước tính {p.rulImageDays ?? "—"} ngày · model {p.modelVersion}</div>}
                {e.type === "HARVEST" && <div className="mt-1 text-xs text-ink-400">{p.quantityKg} kg · {p.variety} · {(p.certifications || []).join(", ")}</div>}
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-400">
                  <span className="inline-flex items-center gap-1">dữ liệu <Hash value={e.dataHash} n={8} tone="plain" /></span>
                  <span className="inline-flex items-center gap-1">vân tay khối <Hash value={e.eventHash} n={8} /></span>
                  <span className="inline-flex items-center gap-1">giao dịch <Hash value={e.txHash} n={8} tone="plain" /></span>
                  <span>RUL lúc ghi: <b className="text-ink-800">{e.rulSnapshot?.rulDaysAtCurrent ?? "—"}</b> ngày</span>
                </div>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Actions({ b }: { b: any }) {
  const qc = useQueryClient();
  const actors = useQuery<any[]>({ queryKey: ["actors"], queryFn: () => api("/meta/actors") });
  const [to, setTo] = useState("");
  const done = () => ["batch", "events", "batches", "rul", "ledger"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const handoff = useMutation({ mutationFn: () => api(`/batches/${b.batchId}/handoff`, { body: { toActorId: to } }), onSuccess: done });
  const sold = useMutation({ mutationFn: () => api(`/batches/${b.batchId}/sold`, { body: {} }), onSuccess: done });
  const opts = (actors.data || []).filter((a) => a.actorId !== b.currentActorId && a.role !== "REGULATOR" && a.role !== "FARMER");
  return (
    <Card title="Bàn giao lô" subtitle="Ghi một sự kiện mới lên sổ cái">
      <label className="label" htmlFor="handoff-to">Giao cho</label>
      <select id="handoff-to" className="input" value={to} onChange={(e) => setTo(e.target.value)}>
        <option value="">Chọn bên nhận</option>
        {opts.map((a) => <option key={a.actorId} value={a.actorId}>{a.name} ({ROLE_LABEL[a.role]})</option>)}
      </select>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn-primary" disabled={!to || handoff.isPending} onClick={() => handoff.mutate()}><Handshake size={15} />Bàn giao</button>
        {b.currentActorRole === "RETAILER" && <button className="btn-secondary" disabled={sold.isPending} onClick={() => { if (confirm("Xác nhận đã bán lô này? Sau khi bán, lô không nhận thêm sự kiện.")) sold.mutate(); }}><ShoppingBag size={15} />Đã bán</button>}
      </div>
      <div className="mt-3"><ErrorBox error={handoff.error || sold.error} /></div>
      {handoff.data && <div className="mt-2 text-sm text-leaf-700">Đã ghi khối #{(handoff.data as any).event.blockNumber} ({(handoff.data as any).event.eventId}).</div>}
    </Card>
  );
}

function SensorTable({ rows, alertTempC }: { rows: any[]; alertTempC?: number }) {
  const [onlyHot, setOnlyHot] = useState(false);
  const shown = [...rows].reverse().filter((r) => !onlyHot || (alertTempC != null && r.tempC > alertTempC));
  return (
    <div>
      <label className="flex items-center gap-2 border-b border-line px-4 py-3 text-sm"><input id="only-hot" type="checkbox" checked={onlyHot} onChange={(e) => setOnlyHot(e.target.checked)} /> Chỉ hiện lần đo vượt ngưỡng {alertTempC}°C</label>
      <div className="max-h-[560px] overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-white"><tr className="border-b border-line"><th className="th">Thời điểm</th><th className="th">Nhiệt độ</th><th className="th">Độ ẩm</th><th className="th">Ethylene</th><th className="th">Vị trí</th><th className="th">Thiết bị</th><th className="th">Chữ ký thiết bị</th></tr></thead>
          <tbody>
            {shown.map((r) => {
              const hot = alertTempC != null && r.tempC > alertTempC;
              return (
                <tr key={r.ts} className={`border-b border-line ${hot ? "bg-danger-50/60" : ""}`}>
                  <td className="td tnum whitespace-nowrap">{fmtTs(r.ts)}</td>
                  <td className={`td tnum font-semibold ${hot ? "text-danger-600" : ""}`}>{r.tempC.toFixed(1)}°C</td>
                  <td className="td tnum">{r.humidityPct}%</td>
                  <td className="td tnum">{r.ethylenePpm.toFixed(1)} ppm</td>
                  <td className="td tnum font-mono text-xs">{r.lat.toFixed(4)}, {r.lon.toFixed(4)}</td>
                  <td className="td font-mono text-xs">{r.deviceId}</td>
                  <td className="td"><Hash value={r.deviceSig} n={8} tone="plain" /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
