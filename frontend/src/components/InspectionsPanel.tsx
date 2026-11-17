/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, fmtTs } from "../api/client";
import { AuthImage, ErrorBox, Freshness, Hash, Spinner } from "./ui";

const days = (v?: number | null) => (v == null ? "—" : `${v.toFixed(2)} ngày`);

export default function InspectionsPanel({ batch, canUpload }: { batch: any; canUpload: boolean }) {
  const qc = useQueryClient();
  const id = batch.batchId;
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const list = useQuery<any[]>({ queryKey: ["inspections", id], queryFn: () => api(`/batches/${id}/inspections`) });
  const models = useQuery<any>({ queryKey: ["models"], queryFn: () => api("/meta/models") });
  const up = useMutation({
    mutationFn: () => { const f = new FormData(); f.append("file", file!); if (note) f.append("note", note); return api(`/batches/${id}/inspections`, { form: f }); },
    onSuccess: () => { setFile(null); setNote(""); ["inspections", "events", "batch", "batches"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); },
  });
  const im = models.data?.imageModel;
  const supported = batch.imageModelSupported;

  return (
    <div className="space-y-5">
      <div className={`rounded-lg border p-3 text-sm ${supported ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
        {supported ? <>Model ảnh: <b className="font-mono">{im?.model?.version}</b> · hợp nhất <b>{models.data?.fusion}</b> (RUL cuối = {models.data?.fusion === "min" ? "min(cảm biến, ảnh)" : models.data?.fusion})</>
          : im?.model ? <>Model ảnh hiện tại không áp dụng cho loại quả này ({batch.fruitId}). Ảnh vẫn được lưu & băm lên sổ cái.</>
            : <>Chưa nạp model ảnh — ảnh vẫn được lưu & băm lên sổ cái, RUL dùng cảm biến (Q10).</>}
        {" "}<Link to="/settings" className="underline">Cài đặt model →</Link>
      </div>

      {canUpload && batch.status !== "SOLD" && (
        <div className="rounded-xl border border-dashed border-slate-300 p-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <div><label className="label">Ảnh kiểm tra</label><input type="file" accept="image/*" className="input" onChange={(e) => setFile(e.target.files?.[0] || null)} /></div>
            <div><label className="label">Ghi chú</label><input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="tuỳ chọn" /></div>
            <button className="btn-primary" disabled={!file || up.isPending} onClick={() => up.mutate()}>{up.isPending ? "Đang xử lý…" : "⬆ Tải lên & dự đoán"}</button>
          </div>
          <div className="mt-3"><ErrorBox error={up.error} /></div>
          {up.data && <div className="mt-3 text-sm text-emerald-700">✔ Đã ghi sự kiện <b>{(up.data as any).eventId}</b> lên sổ cái. RUL cuối: <b>{days((up.data as any).rulFinal)}</b></div>}
        </div>
      )}

      {list.isLoading ? <Spinner /> : !list.data?.length ? <div className="text-sm text-slate-500">Chưa có ảnh kiểm tra.</div> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {list.data.map((i) => (
            <div key={i.inspectionId} className="card p-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="font-mono font-semibold">{i.inspectionId}</span><span className="text-slate-500">{fmtTs(i.ts)}</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div><div className="label">Ảnh gốc</div><AuthImage path={`/batches/${id}/inspections/${i.inspectionId}/image?kind=raw`} alt="raw" className="h-40 w-full rounded object-contain bg-slate-100" /></div>
                <div><div className="label">Đã tiền xử lý</div><AuthImage path={`/batches/${id}/inspections/${i.inspectionId}/image?kind=pre`} alt="pre" className="h-40 w-full rounded object-contain bg-[repeating-conic-gradient(#e2e8f0_0_25%,#fff_0_50%)] bg-[length:16px_16px]" /></div>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-center text-sm">
                <div className="rounded bg-slate-50 p-2"><div className="text-xs text-slate-500">RUL cảm biến</div><b>{days(i.rulSensor)}</b></div>
                <div className="rounded bg-pink-50 p-2"><div className="text-xs text-slate-500">RUL từ ảnh</div><b>{days(i.rulImage)}</b>{i.extra?.model?.rawOutput != null && <div className="text-[10px] text-slate-500">({i.extra.model.rawOutput.toFixed(1)} {i.extra.model.outputUnit === "hours" ? "giờ" : "ngày"} thô)</div>}</div>
                <div className="rounded bg-emerald-50 p-2"><div className="text-xs text-slate-500">RUL cuối</div><b>{days(i.rulFinal)}</b></div>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                <Freshness value={i.freshnessLabel} /> <span>model <span className="font-mono">{i.modelVersion}</span></span> · imageHash <Hash value={i.imageHash} n={8} />
              </div>
              {i.extra?.imageModelError && <div className="mt-1 text-xs text-amber-700">{i.extra.imageModelError}</div>}
              {i.note && <div className="mt-1 text-xs text-slate-500">Ghi chú: {i.note}</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
