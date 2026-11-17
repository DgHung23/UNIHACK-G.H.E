/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Blocks, ExternalLink, Server } from "lucide-react";
import { ago, api, EVENT_LABEL, fmtTs } from "../api/client";
import { Card, ChainLink, ErrorBox, Hash, PageTitle, Spinner } from "../components/ui";
import { EVENT_ICON, EVENT_TONE } from "./Dashboard";

export default function Ledger() {
  const [type, setType] = useState("");
  const [batchId, setBatch] = useState("");
  const [sel, setSel] = useState<any>(null);
  const p = new URLSearchParams();
  if (type) p.set("type", type);
  if (batchId.trim()) p.set("batchId", batchId.trim().toUpperCase());
  const q = useQuery<any>({ queryKey: ["ledger", type, batchId], queryFn: () => api(`/ledger/events?${p}`) });
  const network = useQuery<any>({ queryKey: ["ledger-network"], queryFn: () => api("/ledger/network", { auth: false }), refetchInterval: 30000 });
  const net = network.data;
  const events: any[] = q.data?.events || [];
  useEffect(() => {
    setSel((previous: any) => events.find((event) => event.eventId === previous?.eventId) || events[0] || null);
  }, [q.data]);
  const { eventHash: _e, blockNumber: _b, txHash: _t, prevOk: _p, hashOk: _h, ...core } = sel || {};
  const live = net && net.mode !== "mock";

  return (
    <div>
      <PageTitle eyebrow="Blockchain" sub="Lịch sử các lô theo thứ tự khối; sự kiện liên kết bằng hash riêng cho từng lô.">Sổ cái</PageTitle>

      <section className="mb-6 grid gap-px overflow-hidden rounded-2xl bg-ink-700 text-white shadow-lift md:grid-cols-[1.4fr_1fr_1fr]">
        <div className="bg-ink-900 p-5">
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.1em] text-ink-300"><Server size={14} />Mạng lưu bằng chứng</div>
          <div className="mt-2 font-display text-xl font-semibold">{net ? (live ? net.network : "Sổ cái mô phỏng (offline)") : "…"}</div>
          <p className="mt-1 text-sm text-ink-300">{net?.message}</p>
          <ErrorBox error={network.error} />
        </div>
        <div className="bg-ink-900 p-5">
          <div className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-300">Hợp đồng thông minh</div>
          {net?.contractAddress ? (
            <div className="mt-2 break-all font-mono text-sm">
              {net.explorerUrl ? <a className="inline-flex items-center gap-1 text-cold-300 hover:underline" href={`${net.explorerUrl}/address/${net.contractAddress}`} target="_blank" rel="noreferrer">{net.contractAddress}<ExternalLink size={13} /></a> : net.contractAddress}
            </div>
          ) : <div className="mt-2 text-sm text-ink-300">Chưa triển khai lên mạng công khai</div>}
          {net?.chainId && <div className="mt-1 text-xs text-ink-300">chain ID {net.chainId}</div>}
        </div>
        <div className="bg-ink-900 p-5">
          <div className="text-xs font-semibold uppercase tracking-[0.1em] text-ink-300">Sự kiện đã ghi</div>
          <div className="tnum mt-2 font-display text-3xl font-semibold">{q.data?.count ?? "…"}</div>
          <div className="mt-1 text-xs text-ink-300">khối mới nhất {events[0] ? `#${events[0].blockNumber} · ${ago(events[0].ts)}` : "—"}</div>
        </div>
      </section>

      <ErrorBox error={q.error} />
      <div className="grid gap-5 xl:grid-cols-5">
        <Card className="xl:col-span-3" bodyClass="p-0" title={`${q.data?.count ?? 0} khối`} actions={
          <div className="flex flex-wrap gap-2">
            <input id="ledger-batch" className="input w-40" placeholder="Lọc theo mã lô" value={batchId} onChange={(e) => setBatch(e.target.value)} />
            <select id="ledger-type" className="input w-44" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">Mọi loại sự kiện</option>{Object.entries(EVENT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>}>
          {q.isLoading ? <Spinner /> : (
            <div className="max-h-[680px] overflow-auto">
              <ul className="divide-y divide-line">
                {events.map((e) => {
                  const Icon = EVENT_ICON[e.type] || Blocks;
                  const ok = e.prevOk && e.hashOk;
                  return (
                    <li key={e.eventId}>
                      <button onClick={() => setSel(e)} className={`flex w-full items-center gap-3 px-4 py-3 text-left transition ${sel?.eventId === e.eventId ? "bg-cold-50" : "hover:bg-paper"}`}>
                        <span className="tnum w-24 shrink-0 font-mono text-xs text-ink-400">#{e.blockNumber}</span>
                        <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-lg ${EVENT_TONE[e.type]}`}><Icon size={15} /></span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{EVENT_LABEL[e.type]} <span className="font-mono text-xs font-normal text-ink-400">{e.batchId}</span></span>
                          <span className="tnum block text-xs text-ink-400">{fmtTs(e.ts)}</span>
                        </span>
                        <span className="hidden font-mono text-[11px] text-proof-600 sm:block">{e.eventHash.slice(0, 10)}…</span>
                        <ChainLink ok={ok} />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </Card>
        <Card className="xl:col-span-2" title={sel ? `Khối #${sel.blockNumber}` : "Chọn một khối"} subtitle={sel ? `${EVENT_LABEL[sel.type]} · ${sel.eventId}` : undefined}>
          {sel ? (
            <div className="space-y-3 text-sm">
              <Row k="Lô"><Link to={`/batches/${sel.batchId}`} className="font-mono font-semibold text-cold-700 hover:underline">{sel.batchId}</Link></Row>
              <Row k="Vân tay khối"><Hash value={sel.eventHash} n={14} /></Row>
              <Row k="Vân tay khối trước"><Hash value={sel.prevHash} n={14} tone={sel.prevOk ? "proof" : "bad"} /> <ChainLink ok={sel.prevOk} /></Row>
              <Row k="Vân tay dữ liệu"><Hash value={sel.dataHash} n={14} tone="plain" /></Row>
              <Row k="Mã giao dịch"><Hash value={sel.txHash} n={14} tone="plain" /></Row>
              <Row k="Tính lại vân tay">{sel.hashOk ? <span className="chip bg-leaf-50 text-leaf-700">Khớp nội dung</span> : <span className="chip bg-danger-50 text-danger-600">Không khớp</span>}</Row>
              {net?.explorerTxUrl && sel.txHash && <a className="inline-flex items-center gap-1 font-semibold text-cold-700 hover:underline" href={`${net.explorerTxUrl}${sel.txHash}`} target="_blank" rel="noreferrer">Xem giao dịch trên explorer <ExternalLink size={13} /></a>}
              <div>
                <div className="label mt-2">Nội dung được băm</div>
                <pre className="max-h-[400px] overflow-auto rounded-lg bg-ink-900 p-3 font-mono text-[11.5px] leading-relaxed text-cold-100">{JSON.stringify(core, null, 2)}</pre>
              </div>
            </div>
          ) : <div className="text-sm text-ink-400">Chọn một khối để xem nội dung và mắt xích.</div>}
        </Card>
      </div>
    </div>
  );
}

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-ink-400">{k}</span><span className="flex items-center gap-2">{children}</span></div>;
}
