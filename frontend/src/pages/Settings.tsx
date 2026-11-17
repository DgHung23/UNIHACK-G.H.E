/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, fmtTs } from "../api/client";
import { Card, ErrorBox, Freshness, Hash, PageTitle, Spinner } from "../components/ui";
import FolderBrowser from "../components/FolderBrowser";

const FUSION_HELP: Record<string, string> = {
  min: "Bảo thủ: lấy RUL nhỏ hơn giữa cảm biến và ảnh",
  mean: "Trung bình cộng 2 nguồn",
  sensor_only: "Chỉ dùng RUL cảm biến (Q10)",
  image_only: "Chỉ dùng RUL từ ảnh",
  model: "Model của bạn đã nhận cả 2 đầu vào → lấy thẳng output",
};

export default function Settings() {
  const qc = useQueryClient();
  const status = useQuery<any>({ queryKey: ["model-status"], queryFn: () => api("/settings/model"), refetchInterval: (q) => (q.state.data?.loading ? 1000 : false) });
  const [path, setPath] = useState("");
  const [browse, setBrowse] = useState(false);
  const [info, setInfo] = useState<any>(null);
  const [ckpt, setCkpt] = useState("");
  const [ckInfo, setCkInfo] = useState<any>(null);
  const [fruits, setFruits] = useState<string[]>(["strawberry"]);
  const [unit, setUnit] = useState("auto");
  const [device, setDevice] = useState("auto");
  const [fusion, setFusion] = useState("min");
  const [useSensor, setUseSensor] = useState(true);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    const s = status.data?.settings;
    if (!s || initialized) return;
    if (s.path) setPath(s.path);
    else if (status.data?.defaultModelPath) setPath(status.data.defaultModelPath);
    if (s.checkpoint) setCkpt(s.checkpoint);
    setFusion(s.fusion || "min");
    if (s.fruits?.length) setFruits(s.fruits);
    if (s.outputUnit) setUnit(s.outputUnit);
    if (s.device) setDevice(s.device);
    setUseSensor(s.useSensorInputs !== false);
    setInitialized(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status.data?.settings, status.data?.defaultModelPath]);

  const inspect = useMutation({
    mutationFn: (p: string) => api("/settings/model/inspect", { body: { path: p } }),
    onSuccess: (d: any, inspectedPath) => {
      if (inspectedPath !== path) return;
      const saved = status.data?.settings;
      const selected = saved?.path === inspectedPath && d.checkpoints?.some((c: any) => c.path === saved.checkpoint) ? saved.checkpoint : d.defaultCheckpoint || "";
      setInfo(d); setCkpt(selected); setCkInfo(selected === d.defaultCheckpoint ? d.defaultCheckpointInfo || null : null);
    },
  });
  const ckMeta = useMutation({ mutationFn: (p: string) => api("/settings/model/checkpoint-info", { body: { path: p } }), onSuccess: setCkInfo });
  const native = useMutation({
    mutationFn: () => api("/settings/fs/native-dialog", { body: { initial: path || null } }),
    onSuccess: (d: any) => { if (d.path) selectFolder(d.path); },
  });
  const refresh = () => ["model-status", "models", "batch"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const load = useMutation({
    mutationFn: () => api("/settings/model/load", { body: { path, checkpoint: ckpt || null, device, outputUnit: unit, fruits, fusion, useSensorInputs: useSensor } }),
    onSuccess: refresh,
  });
  const unload = useMutation({ mutationFn: () => api("/settings/model/unload", { method: "POST" }), onSuccess: refresh });
  const saveOpts = useMutation({ mutationFn: () => api("/settings/model/options", { body: { fusion, fruits, useSensorInputs: useSensor } }), onSuccess: refresh });

  const selectFolder = (p: string) => {
    setPath(p); setInfo(null); setCkpt(""); setCkInfo(null);
    inspect.reset(); ckMeta.reset(); load.reset();
  };
  useEffect(() => {
    if (!path.trim()) return;
    const timer = setTimeout(() => inspect.mutate(path), 500);
    return () => clearTimeout(timer);
  }, [path]);
  const pick = (p: string) => { setBrowse(false); selectFolder(p); };
  const st = status.data;
  const m = st?.model;

  return (
    <div className="min-w-0 space-y-5 [overflow-wrap:anywhere]">
      <PageTitle sub="Gắn model RUL từ ảnh đã huấn luyện của bạn — chọn thư mục, nạp và chạy thử">Cài đặt model</PageTitle>
      <ErrorBox error={status.error || unload.error} />

      <Card title="Model đang dùng" actions={m && <button className="btn-secondary" onClick={() => unload.mutate()} disabled={unload.isPending}>Quay về Q10 (không dùng ảnh)</button>}>
        {status.isLoading ? <Spinner /> : m ? (
          <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2 [&>*]:min-w-0">
            <div><div className="label">Trạng thái</div><span className="rounded-full bg-leaf-100 px-2 py-0.5 text-xs font-semibold text-leaf-700">Đã nạp model của bạn</span></div>
            <div><div className="label">Phiên bản</div><span className="font-mono">{m.version}</span></div>
            <div className="sm:col-span-2"><div className="label">Checkpoint</div><span className="mono">{m.checkpoint}</span></div>
            <div><div className="label">modelHash (sha256 trọng số + config)</div><Hash value={m.modelHash} n={16} /></div>
            <div><div className="label">Kiểu / thiết bị</div>{m.kind === "project" ? "Dự án có sẵn (preprocess + predictor gốc)" : "Model rời"} · {m.device}</div>
            <div><div className="label">Output</div>{m.outputUnit === "hours" ? "giờ → đổi sang ngày (÷24)" : "ngày"}{m.meta?.seqLen ? ` · seq_len ${m.meta.seqLen}` : ""}</div>
            <div><div className="label">Áp dụng cho</div>{(m.fruits || []).join(", ") || "mọi loại quả"}</div>
            {m.preprocessFn && <div className="sm:col-span-2"><div className="label">Hàm tiền xử lý</div><span className="mono">{m.preprocessFn}</span></div>}
            {m.meta?.model_key && <div className="sm:col-span-2 break-all text-xs text-ink-400">model_key={m.meta.model_key} · fold={m.meta.fold_name} · val_mae={m.meta.val_mae?.toFixed?.(2)} · {JSON.stringify(m.meta.config)}</div>}
            <div className="text-xs text-ink-400">Nạp lúc {fmtTs(m.loadedAt)} ({m.loadSeconds}s)</div>
          </div>
        ) : (
          <div className="text-sm text-ink-600">Chưa nạp model ảnh — hệ thống dùng <b>Q10</b> (chỉ cảm biến). Ảnh kiểm tra vẫn được lưu và băm lên sổ cái.</div>
        )}
        {st?.error && <div className="mt-3"><ErrorBox error={st.error} /></div>}
      </Card>

      <Card title="1 · Chọn thư mục model">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Đường dẫn thư mục model"
            className="input min-w-0 font-mono"
            value={path}
            onChange={(e) => selectFolder(e.target.value)}
            placeholder={st?.defaultModelPath || "Đường dẫn thư mục model (ví dụ: ml_model)"}
          />
          <div className="flex flex-wrap gap-2">
            {st?.defaultModelPath && (
              <button
                type="button"
                className="btn-secondary whitespace-nowrap"
                title="Dùng model tích hợp sẵn trong repo"
                onClick={() => selectFolder(st.defaultModelPath)}
              >
                Model tích hợp
              </button>
            )}
            <button className="btn-primary whitespace-nowrap" onClick={() => setBrowse(true)}>Duyệt…</button>
            <button className="btn-secondary whitespace-nowrap" title="Mở hộp thoại chọn thư mục của Windows (trên máy chạy backend)" onClick={() => native.mutate()} disabled={native.isPending}>{native.isPending ? "Đang chờ chọn…" : "Hộp thoại Windows"}</button>
            <button className="btn-secondary whitespace-nowrap" disabled={!path || inspect.isPending} onClick={() => inspect.mutate(path)}>Kiểm tra</button>
          </div>
        </div>
        <p className="mt-2 text-xs text-ink-400">Chọn thư mục dự án model tích hợp sẵn hoặc thư mục bất kỳ trên máy bạn (vd. <span className="font-mono">Strawberry-RUL-prediction</span>). Hỗ trợ: dự án có <span className="font-mono">src/&lt;pkg&gt;/services/{"{preprocessing,predictor}"}.py</span>; hoặc model rời <span className="font-mono">.onnx</span> / TorchScript (kèm <span className="font-mono">preprocess.py</span>, <span className="font-mono">fruitchain_model.json</span> tuỳ chọn).</p>
        <div className="mt-3"><ErrorBox error={inspect.error || native.error} /></div>
        {inspect.isPending && <Spinner label="Đang quét thư mục…" />}
        {info && (
          <div className="mt-4 space-y-3">
            <div className={`rounded-lg p-3 text-sm ${info.kind === "project" ? "bg-leaf-50 text-leaf-700" : info.kind === "generic" ? "bg-cold-50 text-cold-900" : "bg-warn-50 text-warn-700"}`}>
              <b>{info.kind === "project" ? "Nhận dạng: dự án model có sẵn" : info.kind === "generic" ? "Model rời" : "Không nhận dạng được model"}</b>
              {info.projectRoot && <div className="mono mt-1">Gốc dự án: {info.projectRoot} (gói {info.package})</div>}
              {info.preprocessFn && <div className="text-xs">Tiền xử lý: <span className="font-mono">{info.preprocessFn}</span></div>}
              {info.predictorClass && <div className="text-xs">Suy luận: <span className="font-mono">{info.predictorClass}</span></div>}
              {info.notes?.map((n: string) => <div key={n} className="text-xs opacity-80">{n}</div>)}
            </div>
            {info.checkpoints?.length > 0 && (
              <div>
                <div className="label">2 · Chọn checkpoint ({info.checkpoints.length})</div>
                <div className="max-h-64 overflow-auto rounded-lg border">
                  {info.checkpoints.map((c: any) => (
                    <label key={c.path} className={`flex cursor-pointer items-center gap-2 border-b px-3 py-1.5 text-sm last:border-0 ${ckpt === c.path ? "bg-brand-50" : "hover:bg-paper"}`}>
                      <input type="radio" checked={ckpt === c.path} onChange={() => { setCkpt(c.path); ckMeta.mutate(c.path); }} />
                      <span className="min-w-0 flex-1 break-all font-mono text-xs">{c.rel}</span>
                      <span className="text-xs text-ink-400">{c.sizeMb} MB · {c.modified}</span>
                    </label>
                  ))}
                </div>
                {ckMeta.isPending ? <Spinner label="Đọc metadata checkpoint…" /> : ckInfo && (
                  <div className="mt-2 rounded bg-paper p-2 text-xs text-ink-600">
                    {ckInfo.error ? <span className="text-danger-600">{ckInfo.error}</span> : <>
                      định dạng <b>{ckInfo.format}</b>{ckInfo.model_key && <> · model <b>{ckInfo.model_key}</b></>}{ckInfo.fold_name && <> · {ckInfo.fold_name}</>}
                      {ckInfo.val_mae != null && <> · val_mae <b>{Number(ckInfo.val_mae).toFixed(2)}</b></>}{ckInfo.epoch != null && <> · epoch {ckInfo.epoch}</>}
                      {ckInfo.config && <div className="break-all font-mono">{JSON.stringify(ckInfo.config)}</div>}
                    </>}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      <Card title="3 · Tuỳ chọn & nạp model">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 [&>*]:min-w-0">
          <div>
            <div className="label">Áp dụng cho loại quả</div>
            <div className="flex flex-wrap gap-3">
              {(st?.fruits || []).map((f: any) => (
                <label key={f.fruitId} className="flex items-center gap-1.5 text-sm">
                  <input type="checkbox" checked={fruits.includes(f.fruitId)} onChange={(e) => setFruits(e.target.checked ? [...fruits, f.fruitId] : fruits.filter((x) => x !== f.fruitId))} />
                  {f.nameVi}
                </label>
              ))}
            </div>
          </div>
          <div>
            <div className="label">Hợp nhất RUL cảm biến + ảnh (FUSION)</div>
            <select className="input" value={fusion} onChange={(e) => setFusion(e.target.value)}>
              {(st?.fusionModes || ["min"]).map((f: string) => <option key={f} value={f}>{f} — {FUSION_HELP[f]}</option>)}
            </select>
          </div>
          <div>
            <div className="label">Đơn vị output của model</div>
            <select className="input" value={unit} onChange={(e) => setUnit(e.target.value)}>
              <option value="auto">Tự động (dự án Strawberry: giờ)</option><option value="hours">Giờ (÷24 → ngày)</option><option value="days">Ngày</option>
            </select>
          </div>
          <div>
            <div className="label">Thiết bị</div>
            <select className="input" value={device} onChange={(e) => setDevice(e.target.value)}>
              <option value="auto">Tự động (CUDA nếu có)</option><option value="cpu">CPU</option><option value="cuda">CUDA (GPU)</option>
            </select>
          </div>
          <label className="block text-sm md:col-span-2">
            <input className="mr-2" type="checkbox" checked={useSensor} onChange={(e) => setUseSensor(e.target.checked)} />
            Truyền nhiệt độ/độ ẩm thật (reading mới nhất của lô) vào model nếu model dùng — model <span className="font-mono">image_only</span> sẽ bỏ qua
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <button className="btn-primary" disabled={!path.trim() || !fruits.length || inspect.isPending || load.isPending || (!!info && !info.checkpoints?.length)} onClick={() => load.mutate()}>{load.isPending ? "Đang nạp model… (vài giây)" : "Nạp model"}</button>
          {m && <button className="btn-secondary" disabled={!fruits.length || saveOpts.isPending} onClick={() => saveOpts.mutate()}>Lưu tuỳ chọn (không nạp lại)</button>}
        </div>
        <div className="mt-3"><ErrorBox error={load.error || saveOpts.error} /></div>
        {load.isSuccess && <div className="mt-2 text-sm text-leaf-700">Đã nạp. Cài đặt được lưu, lần khởi động sau backend tự nạp lại.</div>}
      </Card>

      {m && <TestPanel fruits={m.fruits?.length ? m.fruits : ["strawberry"]} />}
      {browse && <FolderBrowser initial={path || undefined} onPick={pick} onClose={() => setBrowse(false)} />}
    </div>
  );
}

function TestPanel({ fruits }: { fruits: string[] }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fruitId, setFruitId] = useState(fruits[0]);
  const [temp, setTemp] = useState("");
  const [hum, setHum] = useState("");
  const run = useMutation({
    mutationFn: () => {
      const f = new FormData();
      f.append("file", file!); f.append("fruitId", fruitId);
      if (temp) f.append("tempC", temp);
      if (hum) f.append("humidityPct", hum);
      return api("/settings/model/test", { form: f });
    },
  });
  useEffect(() => { if (!file) { setPreview(null); return; } const u = URL.createObjectURL(file); setPreview(u); return () => URL.revokeObjectURL(u); }, [file]);
  const r: any = run.data;
  return (
    <Card title="4 · Chạy thử model (không ghi sổ cái)">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))_auto] sm:items-end [&>*]:min-w-0">
        <div><label className="label">Ảnh</label><input type="file" accept="image/*" className="input" onChange={(e) => setFile(e.target.files?.[0] || null)} /></div>
        <div><label className="label">Loại quả</label><select className="input" value={fruitId} onChange={(e) => setFruitId(e.target.value)}>{fruits.map((f) => <option key={f}>{f}</option>)}</select></div>
        <div><label className="label">Nhiệt độ °C</label><input className="input" value={temp} onChange={(e) => setTemp(e.target.value)} placeholder="tuỳ chọn" /></div>
        <div><label className="label">Độ ẩm %</label><input className="input" value={hum} onChange={(e) => setHum(e.target.value)} placeholder="tuỳ chọn" /></div>
        <button className="btn-primary" disabled={!file || run.isPending} onClick={() => run.mutate()}>{run.isPending ? "Đang chạy…" : "Chạy"}</button>
      </div>
      <div className="mt-3"><ErrorBox error={run.error} /></div>
      {(preview || r) && (
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          <div><div className="label">Ảnh gốc</div>{preview && <img src={preview} className="h-56 w-full rounded bg-paper object-contain" />}</div>
          <div><div className="label">Sau tiền xử lý</div>{r?.preprocessedImage ? <img src={r.preprocessedImage} className="h-56 w-full rounded object-contain bg-[repeating-conic-gradient(#e2e8f0_0_25%,#fff_0_50%)] bg-[length:16px_16px]" /> : <div className="h-56 rounded bg-paper" />}</div>
          <div>
            <div className="label">Kết quả</div>
            {r ? (
              <div className="space-y-2 text-sm">
                <div className="rounded-xl bg-leaf-600 p-4 text-white"><div className="text-xs opacity-80">RUL dự đoán</div><div className="text-3xl font-bold">{r.rulDays.toFixed(2)} ngày</div><div className="text-sm opacity-90">≈ {r.rulHours.toFixed(1)} giờ</div></div>
                <div>Độ tươi: <Freshness value={r.freshness} /> {r.extra?.freshnessDerived && <span className="text-xs text-ink-400">(suy từ RUL / hạn chuẩn)</span>}</div>
                <div className="text-xs text-ink-600">Output thô: {r.extra?.rawOutput} {r.extra?.outputUnit} · tin cậy model {r.extra?.modelConfidence ?? "—"} · tin cậy tách quả {r.preprocess?.confidence ?? "—"}</div>
                <div className="text-xs text-ink-600">Thời gian: preprocess {r.latencyMs.preprocess} ms · suy luận {r.latencyMs.predict} ms</div>
                <div className="text-xs text-ink-400">model <span className="font-mono">{r.modelVersion}</span></div>
              </div>
            ) : <div className="text-sm text-ink-400">Chọn ảnh và bấm Chạy.</div>}
          </div>
        </div>
      )}
    </Card>
  );
}
