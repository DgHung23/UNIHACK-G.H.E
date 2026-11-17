/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, fmtTs } from "../api/client";
import { Card, ErrorBox, PageTitle, Severity, Spinner } from "../components/ui";

export default function Alerts() {
  const qc = useQueryClient();
  const [showAck, setShowAck] = useState(false);
  const alerts = useQuery<any[]>({ queryKey: ["alerts"], queryFn: () => api("/alerts") });
  const ack = useMutation({ mutationFn: (id: string) => api(`/alerts/${id}/ack`, { method: "POST" }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["alerts"] }); qc.invalidateQueries({ queryKey: ["batches"] }); } });
  const rows = (alerts.data || []).filter((a) => showAck || !a.acknowledged);
  return (
    <div>
      <PageTitle sub="Vi phạm chuỗi lạnh và RUL thấp">Cảnh báo</PageTitle>
      <Card actions={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showAck} onChange={(e) => setShowAck(e.target.checked)} /> Hiện cả cảnh báo đã xác nhận</label>} title={`${rows.length} cảnh báo`}>
        {alerts.isLoading ? <Spinner /> : (
          <div className="space-y-2">
            <ErrorBox error={ack.error} />
            {rows.map((a) => (
              <div key={a.alertId} className={`flex flex-wrap items-center gap-3 rounded-lg border p-3 ${a.acknowledged ? "opacity-60" : ""} ${a.severity === "HIGH" ? "border-red-200" : "border-amber-200"}`}>
                <Severity value={a.severity} />
                <span className="text-lg">{a.type === "COLD_CHAIN_VIOLATION" ? "🌡️" : "⏳"}</span>
                <div className="min-w-[200px] flex-1">
                  <div className="text-sm font-medium">{a.message}</div>
                  <div className="text-xs text-slate-500"><Link to={`/batches/${a.batchId}`} className="font-mono text-brand-700 hover:underline">{a.batchId}</Link> · {fmtTs(a.ts)} · {a.alertId}{a.relatedEventId ? ` · ${a.relatedEventId}` : ""}</div>
                </div>
                {a.acknowledged ? <span className="text-xs text-slate-500">✔ đã xác nhận</span> : <button className="btn-secondary" onClick={() => ack.mutate(a.alertId)} disabled={ack.isPending}>Xác nhận</button>}
              </div>
            ))}
            {!rows.length && <div className="p-6 text-center text-sm text-slate-500">Không có cảnh báo 🎉</div>}
          </div>
        )}
      </Card>
    </div>
  );
}
