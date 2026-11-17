/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, EVENT_LABEL, fmtTs } from "../api/client";
import { Card, ErrorBox, Hash, PageTitle, Spinner } from "../components/ui";

export default function Ledger() {
  const [type, setType] = useState("");
  const [batchId, setBatch] = useState("");
  const [sel, setSel] = useState<any>(null);
  const p = new URLSearchParams();
  if (type) p.set("type", type);
  if (batchId) p.set("batchId", batchId);
  const q = useQuery<any>({ queryKey: ["ledger", type, batchId], queryFn: () => api(`/ledger/events?${p}`) });
  const network = useQuery<any>({ queryKey: ["ledger-network"], queryFn: () => api("/ledger/network"), refetchInterval: 30000 });
  const net = network.data;
  const { eventHash: _e, blockNumber: _b, txHash: _t, prevOk: _p, hashOk: _h, ...core } = sel || {};
  return (
    <div>
      <PageTitle sub={`Mọi sự kiện đã ghi — chế độ sổ cái: ${q.data?.mode ?? "…"}`}>Trình khám phá sổ cái</PageTitle>
      <div className="mb-5">
        <Card title={net?.network || "Kết nối blockchain"}>
          <ErrorBox error={network.error} />
          {net && <div className="space-y-2 text-sm">
            <div className={`font-semibold ${net.isCompetitionNetwork && net.ready ? "text-emerald-700" : "text-amber-700"}`}>
              {net.mode === "mock" ? "Demo offline · chưa ghi lên Avalanche" : net.ready ? "Đã kết nối hợp đồng" : "Chưa sẵn sàng"}
              {net.chainId && <span className="ml-2 font-mono">chain ID {net.chainId}</span>}
            </div>
            <p className="text-slate-600">{net.message}</p>
            {net.contractAddress && <div className="break-all">Hợp đồng: {net.explorerUrl ? <a href={`${net.explorerUrl}/address/${net.contractAddress}`} target="_blank" rel="noreferrer" className="font-mono text-brand-700 underline">{net.contractAddress} ↗</a> : <span className="font-mono">{net.contractAddress}</span>}</div>}
            <div className="text-xs text-slate-500">{net.trustModel}</div>
          </div>}
        </Card>
      </div>
      <ErrorBox error={q.error} />
      <div className="grid gap-5 lg:grid-cols-5">
        <Card className="lg:col-span-3" title={`${q.data?.count ?? 0} sự kiện`} actions={
          <div className="flex gap-2">
            <input className="input w-36" placeholder="Mã lô" value={batchId} onChange={(e) => setBatch(e.target.value)} />
            <select className="input w-40" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">Mọi loại</option>{Object.entries(EVENT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>}>
          {q.isLoading ? <Spinner /> : (
            <div className="max-h-[640px] overflow-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-white"><tr className="border-b"><th className="th">Block</th><th className="th">Sự kiện</th><th className="th">Lô</th><th className="th">Thời điểm</th><th className="th">Liên kết</th></tr></thead>
                <tbody>
                  {(q.data?.events || []).map((e: any) => (
                    <tr key={e.eventId} onClick={() => setSel(e)} className={`cursor-pointer border-b hover:bg-slate-50 ${sel?.eventId === e.eventId ? "bg-brand-50" : ""}`}>
                      <td className="td font-mono text-xs">#{e.blockNumber}</td>
                      <td className="td"><div className="font-medium">{EVENT_LABEL[e.type] || e.type}</div><div className="font-mono text-xs text-slate-400">{e.eventId}</div></td>
                      <td className="td"><Link onClick={(ev) => ev.stopPropagation()} to={`/batches/${e.batchId}`} className="font-mono text-xs text-brand-700 hover:underline">{e.batchId}</Link></td>
                      <td className="td whitespace-nowrap text-xs">{fmtTs(e.ts)}</td>
                      <td className="td">{e.prevOk && e.hashOk ? <span className="text-emerald-600">✔</span> : <span className="font-bold text-red-600">✘</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card className="lg:col-span-2" title={sel ? `Chi tiết ${sel.eventId}` : "Chọn một sự kiện"}>
          {sel ? (
            <div className="space-y-2 text-sm">
              <div>eventHash: <Hash value={sel.eventHash} n={16} /></div>
              <div>prevHash: <Hash value={sel.prevHash} n={16} /> {sel.prevOk ? <span className="text-emerald-600">✔ khớp sự kiện trước</span> : <span className="text-red-600">✘</span>}</div>
              <div>txHash: <Hash value={sel.txHash} n={16} /></div>
              {net?.explorerTxUrl && <a className="inline-block text-brand-700 underline" href={`${net.explorerTxUrl}${sel.txHash}`} target="_blank" rel="noreferrer">Xem giao dịch trên Avalanche Explorer ↗</a>}
              <div>Hash tính lại: {sel.hashOk ? <span className="text-emerald-600">✔ khớp eventHash</span> : <span className="text-red-600">✘ không khớp</span>}</div>
              <div className="label mt-3">Nội dung được băm (canonical JSON)</div>
              <pre className="max-h-[440px] overflow-auto rounded bg-slate-900 p-3 text-xs text-emerald-200">{JSON.stringify(core, null, 2)}</pre>
            </div>
          ) : <div className="text-sm text-slate-500">Bấm vào một dòng để xem JSON và trạng thái liên kết hash.</div>}
        </Card>
      </div>
    </div>
  );
}
