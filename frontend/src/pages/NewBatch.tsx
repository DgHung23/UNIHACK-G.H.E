/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { Card, ErrorBox, PageTitle } from "../components/ui";

export default function NewBatch() {
  const { user } = useAuth();
  const nav = useNavigate();
  const fruits = useQuery<any[]>({ queryKey: ["fruits"], queryFn: () => api("/meta/fruits") });
  const actors = useQuery<any[]>({ queryKey: ["actors"], queryFn: () => api("/meta/actors") });
  const farms = (actors.data || []).filter((a) => a.role === "FARMER" && (user?.role === "ADMIN" || a.actorId === user?.actorId));
  const [f, setF] = useState<any>({ fruitId: "", variety: "", farmId: user?.actorId || "", quantityKg: 100, certifications: "VietGAP" });
  const create = useMutation({
    mutationFn: () => api("/batches", { body: { ...f, quantityKg: Number(f.quantityKg), certifications: f.certifications.split(",").map((s: string) => s.trim()).filter(Boolean) } }),
    onSuccess: (b: any) => nav(`/batches/${b.batchId}`),
  });
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  return (
    <div className="max-w-2xl">
      <PageTitle sub="Sinh metadataHash, QR và ghi sự kiện HARVEST lên sổ cái">Tạo lô mới</PageTitle>
      <Card>
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <div><label className="label">Loại quả</label>
            <select className="input" required value={f.fruitId} onChange={(e) => { const fr = fruits.data?.find((x) => x.fruitId === e.target.value); setF({ ...f, fruitId: e.target.value, variety: f.variety || fr?.nameVi || "" }); }}>
              <option value="">— chọn —</option>{(fruits.data || []).map((x) => <option key={x.fruitId} value={x.fruitId}>{x.nameVi}</option>)}
            </select></div>
          <div><label className="label">Giống</label><input className="input" required value={f.variety} onChange={set("variety")} /></div>
          <div><label className="label">Nông hộ</label>
            <select className="input" required value={f.farmId} onChange={set("farmId")}>
              <option value="">— chọn —</option>{farms.map((a) => <option key={a.actorId} value={a.actorId}>{a.name}</option>)}
            </select></div>
          <div><label className="label">Khối lượng (kg)</label><input type="number" min={1} className="input" required value={f.quantityKg} onChange={set("quantityKg")} /></div>
          <div className="sm:col-span-2"><label className="label">Chứng nhận (phân cách bằng dấu phẩy)</label><input className="input" value={f.certifications} onChange={set("certifications")} /></div>
          <div className="sm:col-span-2"><ErrorBox error={create.error} /></div>
          <div className="sm:col-span-2"><button className="btn-primary" disabled={create.isPending}>{create.isPending ? "Đang tạo…" : "Tạo lô & ghi HARVEST"}</button></div>
        </form>
      </Card>
    </div>
  );
}
