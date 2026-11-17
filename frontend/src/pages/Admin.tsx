/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, fmtTs } from "../api/client";
import { Card, ErrorBox, Hash, PageTitle } from "../components/ui";

export default function Admin() {
  const qc = useQueryClient();
  const models = useQuery<any>({ queryKey: ["models"], queryFn: () => api("/meta/models") });
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  const all = () => qc.invalidateQueries();
  const seed = useMutation({ mutationFn: () => api("/admin/seed", { method: "POST" }), onSuccess: all });
  const reset = useMutation({ mutationFn: () => api("/admin/reset", { method: "POST" }), onSuccess: all });
  const tick = useMutation({ mutationFn: () => api("/admin/simulate/tick", { method: "POST" }), onSuccess: all });
  const [fruitId, setFruitId] = useState("mango");
  const [temps, setTemps] = useState("13,13,13,13,25,25,25,25,25,25,13,13,13");
  const whatif = useMutation({ mutationFn: () => api("/rul/predict", { body: { fruitId, readings: temps.split(/[,\s]+/).filter(Boolean).map((t) => ({ tempC: Number(t) })) } }) });

  return (
    <div className="space-y-5">
      <PageTitle>Quản trị</PageTitle>
      <Card title="Dữ liệu demo">
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={() => { if (confirm("Xoá toàn bộ và nạp lại dữ liệu demo?")) seed.mutate(); }} disabled={seed.isPending}>Nạp lại demo</button>
          <button className="btn-danger" onClick={() => { if (confirm("Xoá TOÀN BỘ dữ liệu (kể cả tài khoản)?")) reset.mutate(); }} disabled={reset.isPending}>Reset</button>
          <button className="btn-secondary" onClick={() => tick.mutate()} disabled={tick.isPending}>Simulate tick (+1 giờ)</button>
        </div>
        <div className="mt-3"><ErrorBox error={seed.error || reset.error || tick.error} /></div>
        {seed.data && <div className="mt-2 text-sm text-leaf-700">{JSON.stringify((seed.data as any).counts)}</div>}
        {tick.data && <div className="mt-2 text-xs text-ink-600">{Object.entries((tick.data as any).batches).map(([k, v]: any) => `${k}: ${fmtTs(v.ts)} RUL ${v.rulDaysAtCurrent}${v.violations.length ? " ⚠ vi phạm" : ""}`).join(" · ")}</div>}
      </Card>
      <Card title="Phiên bản mô hình">
        <table className="w-full">
          <thead><tr className="border-b"><th className="th">Phiên bản</th><th className="th">Loại</th><th className="th">modelHash</th><th className="th">Đăng ký</th></tr></thead>
          <tbody>{(models.data?.versions || []).map((m: any) => (
            <tr key={m.version} className="border-b"><td className="td font-mono text-xs">{m.version}</td><td className="td">{m.kind === "image" ? "ảnh" : "cảm biến"}</td><td className="td"><Hash value={m.modelHash} n={12} /></td><td className="td text-xs">{fmtTs(m.registeredTs)}</td></tr>
          ))}</tbody>
        </table>
      </Card>
      <Card title="What-if: dự đoán RUL theo chuỗi nhiệt độ (mỗi giá trị = 1 giờ)">
        <div className="grid gap-2 sm:grid-cols-[160px_1fr_auto]">
          <select className="input" value={fruitId} onChange={(e) => setFruitId(e.target.value)}>{(fruits.data || []).map((f) => <option key={f.fruitId} value={f.fruitId}>{f.nameVi}</option>)}</select>
          <input className="input font-mono" value={temps} onChange={(e) => setTemps(e.target.value)} />
          <button className="btn-primary" onClick={() => whatif.mutate()}>Tính</button>
        </div>
        <ErrorBox error={whatif.error} />
        {whatif.data && (
          <div className="mt-3 h-56">
            <ResponsiveContainer>
              <LineChart data={(whatif.data as any).series.map((s: any, i: number) => ({ ...s, h: i }))}>
                <XAxis dataKey="h" tick={{ fontSize: 11 }} label={{ value: "giờ", position: "insideBottomRight", fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} width={32} />
                <Tooltip />
                <Line dataKey="rulDaysAtCurrent" name="RUL hiện tại" stroke="#059669" isAnimationActive={false} />
                <Line dataKey="rulDaysAtOptimal" name="RUL nếu chuẩn" stroke="#6366f1" strokeDasharray="5 4" isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}
