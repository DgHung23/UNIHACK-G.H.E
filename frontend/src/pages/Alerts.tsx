/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellOff, Check, Hourglass, Thermometer } from "lucide-react";
import { ago, api, fmtTs } from "../api/client";
import { Card, Empty, ErrorBox, PageTitle, Severity, Spinner } from "../components/ui";

export default function Alerts() {
  const qc = useQueryClient();
  const [showAck, setShowAck] = useState(false);
  const alerts = useQuery<any[]>({ queryKey: ["alerts"], queryFn: () => api("/alerts") });
  const ack = useMutation({ mutationFn: (id: string) => api(`/alerts/${id}/ack`, { method: "POST" }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["alerts"] }); qc.invalidateQueries({ queryKey: ["batches"] }); } });
  const all = alerts.data || [];
  const rows = all.filter((a) => showAck || !a.acknowledged);
  const openN = all.filter((a) => !a.acknowledged).length;
  return (
    <div>
      <PageTitle eyebrow="Giám sát" sub={`${openN} cảnh báo chưa xử lý · sự cố chuỗi lạnh và lô sắp hết hạn`}>Cảnh báo</PageTitle>
      <ErrorBox error={alerts.error || ack.error} />
      <Card bodyClass="p-0" title={showAck ? "Tất cả cảnh báo" : "Chưa xử lý"}
        actions={<label className="flex items-center gap-2 text-sm text-ink-600"><input id="show-ack" type="checkbox" checked={showAck} onChange={(e) => setShowAck(e.target.checked)} />Hiện cả cảnh báo đã xác nhận</label>}>
        {alerts.isLoading ? <Spinner /> : !rows.length ? (
          <Empty icon={<BellOff size={20} />} title="Không có cảnh báo nào cần xử lý">Mọi lô đang trong ngưỡng nhiệt độ an toàn.</Empty>
        ) : (
          <ul className="divide-y divide-line">
            {rows.map((a) => {
              const cold = a.type === "COLD_CHAIN_VIOLATION";
              return (
                <li key={a.alertId} className={`flex flex-wrap items-center gap-4 px-5 py-4 ${a.acknowledged ? "opacity-55" : ""}`}>
                  <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl ${cold ? "bg-danger-50 text-danger-600" : "bg-warn-50 text-warn-600"}`}>{cold ? <Thermometer size={18} /> : <Hourglass size={18} />}</span>
                  <div className="min-w-[220px] flex-1">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{cold ? "Sự cố chuỗi lạnh" : "Sắp hết hạn"}</span><Severity value={a.severity} /></div>
                    <div className="text-sm text-ink-600">{a.message}</div>
                    <div className="mt-0.5 text-xs text-ink-400"><Link to={`/batches/${a.batchId}`} className="font-mono font-semibold text-cold-700 hover:underline">{a.batchId}</Link> · {fmtTs(a.ts)} ({ago(a.ts)}){a.relatedEventId ? ` · khối ${a.relatedEventId}` : ""}</div>
                  </div>
                  {a.acknowledged
                    ? <span className="inline-flex items-center gap-1 text-xs text-ink-400"><Check size={13} />Đã xác nhận</span>
                    : <button className="btn-secondary" onClick={() => ack.mutate(a.alertId)} disabled={ack.isPending}><Check size={15} />Xác nhận</button>}
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </div>
  );
}
