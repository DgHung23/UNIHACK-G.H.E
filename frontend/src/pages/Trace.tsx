/* eslint-disable @typescript-eslint/no-explicit-any */
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, EVENT_LABEL, fmtTs, FRESH_COLORS, STATUS_LABEL } from "../api/client";
import { Freshness, Spinner } from "../components/ui";

export default function Trace() {
  const { batchId = "" } = useParams();
  const q = useQuery<any>({ queryKey: ["trace", batchId], queryFn: () => api(`/public/trace/${batchId}`, { auth: false }) });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <div className="p-6 text-center text-slate-600">Không tìm thấy lô <b>{batchId}</b>.</div>;
  const t = q.data;
  const ok = t.verification.overall === "PASS";
  const fresh = t.latestRul?.freshness;
  return (
    <div className="mx-auto min-h-screen max-w-xl bg-slate-50 pb-10">
      <header className="bg-brand-700 px-4 pb-6 pt-5 text-white">
        <div className="text-sm opacity-80">🍓 FruitChain · Truy xuất nguồn gốc</div>
        <h1 className="mt-1 text-2xl font-bold">{t.productName}</h1>
        <div className="text-sm opacity-90">{t.variety} · lô <span className="font-mono">{t.batchId}</span></div>
      </header>
      <div className="-mt-4 space-y-4 px-4">
        <div className={`rounded-xl p-4 text-white shadow ${ok ? "bg-emerald-600" : "bg-red-600"}`}>
          <div className="text-lg font-bold">{ok ? "✔ Đã xác minh toàn vẹn" : "⚠ Phát hiện sai lệch dữ liệu"}</div>
          <div className="text-xs opacity-90">{ok ? "Dữ liệu khớp với bằng chứng đã ghi trong sổ cái." : `${t.verification.segmentsMismatched} đoạn dữ liệu không khớp với bằng chứng trong sổ cái.`} Kiểm tra lúc {fmtTs(t.verification.checkedAt)}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
          <b>{t.ledgerNetwork?.network}</b> · {t.ledgerNetwork?.mode === "mock" ? "Dữ liệu demo offline, chưa được xác thực trên Avalanche." : t.ledgerNetwork?.message}
          {t.ledgerNetwork?.contractAddress && t.ledgerNetwork?.explorerUrl && <a href={`${t.ledgerNetwork.explorerUrl}/address/${t.ledgerNetwork.contractAddress}`} className="mt-1 block break-all text-brand-700 underline" target="_blank" rel="noreferrer">Hợp đồng: {t.ledgerNetwork.contractAddress} ↗</a>}
        </div>
        <div className="card grid grid-cols-2 gap-3 p-4 text-sm">
          <div><div className="label">Nguồn gốc</div>{t.farmName}<div className="text-xs text-slate-500">{t.originProvince}</div></div>
          <div><div className="label">Thu hoạch</div>{fmtTs(t.harvestTs)}</div>
          <div><div className="label">Chứng nhận</div>{(t.certifications || []).join(", ") || "—"}</div>
          <div><div className="label">Trạng thái</div>{STATUS_LABEL[t.status] || t.status}</div>
          <div className="col-span-2">
            <div className="label">Hạn dùng còn lại (ước tính)</div>
            <div className="flex items-baseline gap-2"><span className="text-3xl font-bold" style={{ color: FRESH_COLORS[fresh] }}>{t.latestRul?.rulDaysAtCurrent?.toFixed(1)}</span> ngày <Freshness value={fresh} /></div>
            <div className="text-xs text-slate-500">Nếu bảo quản đúng chuẩn: {t.latestRul?.rulDaysAtOptimal?.toFixed(1)} ngày</div>
          </div>
        </div>
        <div className="card p-4">
          <div className="label">Đường cong hạn dùng</div>
          <div className="h-44">
            <ResponsiveContainer>
              <AreaChart data={t.rulCurve}>
                <XAxis dataKey="ts" hide />
                <YAxis width={28} tick={{ fontSize: 10 }} />
                <Tooltip labelFormatter={(l) => fmtTs(l as string)} formatter={(v: any) => [`${v} ngày`, "RUL"]} />
                <Area dataKey="rulDaysAtCurrent" stroke="#059669" fill="#a7f3d0" isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card p-4">
          <div className="label mb-2">Hành trình</div>
          <ol className="relative ml-2 border-l border-slate-200">
            {t.timeline.map((e: any, i: number) => (
              <li key={i} className="mb-4 ml-4">
                <span className={`absolute -left-[6px] mt-1.5 h-3 w-3 rounded-full ${e.type === "VIOLATION" ? "bg-red-500" : "bg-brand-500"}`} />
                <div className="text-sm font-semibold">{EVENT_LABEL[e.type] || e.type}</div>
                <div className="text-xs text-slate-500">{fmtTs(e.ts)}</div>
                <div className="text-sm">{e.actorName}{e.toActorName ? ` → ${e.toActorName}` : ""}</div>
                {e.violation && <div className="text-xs text-red-600">Nhiệt độ vượt {e.violation.thresholdC}°C trong {e.violation.durationHours} giờ (tối đa {e.violation.maxTempC}°C)</div>}
                <div className="font-mono text-[10px] text-slate-400">block #{e.blockNumber} · tx {e.txHash ? `${e.txHash.slice(0, 14)}…` : "thiếu bằng chứng"}</div>
                {t.ledgerNetwork?.explorerTxUrl && e.txHash && <a href={`${t.ledgerNetwork.explorerTxUrl}${e.txHash}`} target="_blank" rel="noreferrer" className="text-xs text-brand-700 underline">Kiểm tra giao dịch ↗</a>}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
