/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Award, Blocks, Calendar, ExternalLink, MapPin, ShieldCheck } from "lucide-react";
import { api, EVENT_LABEL, fmtShort, fmtTs, FRESH_COLORS, FRUIT_COLOR, STATUS_LABEL } from "../api/client";
import { Freshness, Logo, Spinner } from "../components/ui";
import { EVENT_ICON, EVENT_TONE } from "./Dashboard";

export default function Trace() {
  const { batchId = "" } = useParams();
  const q = useQuery<any>({ queryKey: ["trace", batchId], queryFn: () => api(`/public/trace/${batchId}`, { auth: false }) });
  if (q.isLoading) return <div className="grid min-h-screen place-items-center"><Spinner /></div>;
  if (q.error) return <div className="grid min-h-screen place-items-center p-6 text-center text-ink-600">Không tìm thấy lô <b className="font-mono">{batchId}</b>.</div>;
  const t = q.data;
  const fresh = t.latestRul?.freshness;
  const net = t.ledgerNetwork;
  const color = FRUIT_COLOR[t.fruitId] || "#1a7f93";

  return (
    <div className="mx-auto min-h-screen max-w-md bg-paper pb-12">
      <header className="relative overflow-hidden bg-ink-900 px-5 pb-16 pt-5 text-white">
        <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full opacity-30" style={{ background: color }} />
        <div className="relative flex items-center justify-between"><Logo light size={24} /><span className="text-[11px] text-ink-300">Truy xuất nguồn gốc</span></div>
        <div className="relative mt-6 font-mono text-xs text-ink-300">{t.batchId}</div>
        <h1 className="relative text-[28px] font-semibold leading-tight">{t.productName}</h1>
        <div className="relative text-sm text-ink-300">{t.variety} · {t.quantityKg?.toLocaleString("vi-VN")} kg</div>
      </header>

      <div className="-mt-10 space-y-4 px-4">
        <div className="relative rounded-2xl bg-white p-4 shadow-lift border border-line">
          <div className="flex items-center gap-3">
            <Blocks size={28} className="shrink-0 text-proof-600" />
            <div>
              <div className="font-display text-lg font-semibold">Hồ sơ nguồn gốc</div>
              <div className="text-xs text-ink-500">{t.timeline.length} mốc trong hành trình lô hàng</div>
            </div>
          </div>
          <div className="mt-3 border-t border-line pt-2 text-[11px] text-ink-500">
            {net?.mode === "mock" ? "Sổ cái cục bộ · chưa ghi lên Avalanche" : net?.network}
            {net?.contractAddress && net?.explorerUrl && <a href={`${net.explorerUrl}/address/${net.contractAddress}`} target="_blank" rel="noreferrer" className="ml-1 inline-flex items-center gap-0.5 underline">tự kiểm tra trên explorer<ExternalLink size={11} /></a>}
          </div>
        </div>

        <div className="card p-4">
          <div className="text-xs font-medium text-ink-400">Còn dùng được khoảng</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="tnum font-display text-5xl font-semibold" style={{ color: FRESH_COLORS[fresh] || "#0d1c17" }}>{t.latestRul?.rulDaysAtCurrent?.toFixed(1)}</span>
            <span className="text-ink-600">ngày</span><Freshness value={fresh} />
          </div>
          <div className="mt-1 text-xs text-ink-400">Nếu bảo quản đúng nhiệt độ khuyến nghị: {t.latestRul?.rulDaysAtOptimal?.toFixed(1)} ngày</div>
          <div className="mt-3 h-32">
            <ResponsiveContainer>
              <AreaChart data={t.rulCurve} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
                <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1a7f93" stopOpacity={0.35} /><stop offset="1" stopColor="#1a7f93" stopOpacity={0} /></linearGradient></defs>
                <XAxis dataKey="ts" hide /><YAxis hide />
                <Tooltip labelFormatter={(l) => fmtTs(l as string)} formatter={(v: any) => [`${v} ngày`, "Hạn dùng còn lại"]} />
                <Area dataKey="rulDaysAtCurrent" stroke="#0f6a7c" strokeWidth={2} fill="url(#g)" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card divide-y divide-line">
          <Fact icon={<MapPin size={16} />} k="Nguồn gốc">{t.farmName}, {t.originProvince}</Fact>
          <Fact icon={<Calendar size={16} />} k="Thu hoạch">{fmtTs(t.harvestTs)}</Fact>
          <Fact icon={<Award size={16} />} k="Chứng nhận">{(t.certifications || []).join(", ") || "—"}</Fact>
          <Fact icon={<ShieldCheck size={16} />} k="Hiện tại">{STATUS_LABEL[t.status] || t.status}{t.currentHolder ? ` · ${t.currentHolder}` : ""}</Fact>
        </div>

        <div className="card p-4">
          <div className="mb-3 font-display font-semibold">Hành trình</div>
          <ol className="relative">
            {t.timeline.map((e: any, i: number) => {
              const Icon = EVENT_ICON[e.type];
              const last = i === t.timeline.length - 1;
              return (
                <li key={i} className="relative flex gap-3 pb-4">
                  {!last && <span className="absolute left-4 top-9 h-[calc(100%-28px)] w-px bg-line" />}
                  <span className={`relative grid h-8 w-8 shrink-0 place-items-center rounded-full ${EVENT_TONE[e.type]}`}>{Icon && <Icon size={15} />}</span>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold">{EVENT_LABEL[e.type] || e.type}</div>
                    <div className="text-sm text-ink-600">{e.actorName}{e.toActorName ? ` → ${e.toActorName}` : ""}</div>
                    {e.violation && <div className="text-xs font-medium text-danger-600">Nhiệt độ vượt {e.violation.thresholdC}°C trong {e.violation.durationHours} giờ</div>}
                    <div className="text-xs text-ink-400">{fmtTs(e.ts)}</div>
                    {net?.explorerTxUrl && e.txHash && <a href={`${net.explorerTxUrl}${e.txHash}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-xs font-semibold text-cold-700">Xem bằng chứng<ExternalLink size={11} /></a>}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
        <p className="px-2 text-center text-[11px] leading-relaxed text-ink-400">Dữ liệu cảm biến và ảnh lưu tại hệ thống FruitChain; vân tay của chúng được khoá trên sổ cái để bất kỳ ai cũng kiểm tra được.</p>
      </div>
    </div>
  );
}

function Fact({ icon, k, children }: { icon: React.ReactNode; k: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 px-4 py-3">
      <span className="mt-0.5 text-cold-600">{icon}</span>
      <div className="min-w-0"><div className="text-xs text-ink-400">{k}</div><div className="text-sm font-medium">{children}</div></div>
    </div>
  );
}
