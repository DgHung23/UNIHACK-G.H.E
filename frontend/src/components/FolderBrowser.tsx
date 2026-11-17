/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Brain, CornerLeftUp, FileText, Folder, FolderOpen, HardDrive, Star, X } from "lucide-react";
import { api } from "../api/client";
import { ErrorBox, Spinner } from "./ui";

/** Hộp thoại duyệt thư mục trên MÁY CHẠY BACKEND (trình duyệt không cho đọc đường dẫn thật của thư mục). */
export default function FolderBrowser({ initial, onPick, onClose }: { initial?: string; onPick: (path: string) => void; onClose: () => void }) {
  const [path, setPath] = useState<string | null>(initial || null);
  const [typed, setTyped] = useState(initial || "");
  const q = useQuery<any>({ queryKey: ["fs", path], queryFn: () => api(`/settings/fs${path ? `?path=${encodeURIComponent(path)}` : ""}`) });
  useEffect(() => { if (q.data?.path) setTyped(q.data.path); }, [q.data?.path]);
  const d = q.data;
  const crumbs = d?.path ? splitPath(d.path) : [];

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="folder-dialog-title" className="card flex min-w-0 max-h-[88vh] w-full max-w-3xl flex-col [overflow-wrap:anywhere]" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 id="folder-dialog-title" className="inline-flex font-semibold items-center gap-2"><FolderOpen size={18} className="text-cold-600" />Chọn thư mục model</h3>
          <button aria-label="Đóng hộp chọn thư mục" className="text-ink-400 hover:text-ink-900" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="space-y-3 border-b p-4">
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setPath(typed.trim() || null); }}>
            <input aria-label="Đường dẫn thư mục" className="input min-w-0 font-mono" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Dán đường dẫn thư mục model..." />
            <button className="btn-secondary">Đi</button>
          </form>
          <div className="flex flex-wrap gap-1.5">
            {(d?.drives || []).map((dr: string) => <button key={dr} className="rounded border px-2 py-0.5 text-xs hover:bg-paper" onClick={() => setPath(dr)}><HardDrive size={12} className="mr-1 inline" />{dr}</button>)}
            {(d?.shortcuts || []).map((s: any) => <button key={s.path} className="rounded border px-2 py-0.5 text-xs hover:bg-paper" title={s.path} onClick={() => setPath(s.path)}><Star size={12} className="mr-1 inline" />{s.name}</button>)}
          </div>
          {crumbs.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 text-sm">
              {crumbs.map((c, i) => (
                <span key={c.path} className="flex items-center gap-1">
                  {i > 0 && <span className="text-ink-400">›</span>}
                  <button className="rounded px-1 hover:bg-paper font-medium text-brand-700" onClick={() => setPath(c.path)}>{c.name}</button>
                </span>
              ))}
            </div>
          )}
          {d?.projectRoot && (
            <div className="break-all rounded-lg bg-leaf-50 p-2 text-xs text-leaf-700">Nằm trong dự án model: <span className="font-mono">{d.projectRoot}</span> (có preprocess + predictor)</div>
          )}
        </div>
        <div className="min-h-[240px] flex-1 overflow-auto p-2">
          {q.isLoading ? <Spinner /> : q.error ? <div className="p-2"><ErrorBox error={q.error} /></div> : !d?.path ? (
            <div className="p-4 text-sm text-ink-400">Chọn ổ đĩa hoặc lối tắt ở trên để bắt đầu.</div>
          ) : (
            <ul>
              {d.parent && <li><button className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-sm hover:bg-paper" onClick={() => setPath(d.parent)}><CornerLeftUp size={15} className="text-ink-400" />..</button></li>}
              {d.entries.map((e: any) => (
                <li key={e.path}>
                  {e.isDir ? (
                    <button className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-sm hover:bg-paper" onDoubleClick={() => setPath(e.path)} onClick={() => setPath(e.path)}><Folder size={15} className="text-cold-500" />{e.name}</button>
                  ) : (
                    <div className="flex items-center gap-2 px-3 py-1.5 text-sm text-ink-600">{e.isModel ? <Brain size={15} className="text-proof-500" /> : <FileText size={15} className="text-ink-400" />} {e.name} {e.sizeMb != null && <span className="text-xs text-ink-400">{e.sizeMb} MB</span>}</div>
                  )}
                </li>
              ))}
              {!d.entries.length && <li className="px-3 py-2 text-sm text-ink-400">(thư mục trống)</li>}
            </ul>
          )}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t p-4">
          <div className="text-xs text-ink-400">{d?.path ? <>Đang chọn: <span className="font-mono">{d.path}</span>{d.modelFilesHere ? ` · ${d.modelFilesHere} file model` : ""}</> : ""}</div>
          <div className="flex gap-2">
            <button className="btn-secondary" onClick={onClose}>Huỷ</button>
            <button className="btn-primary" disabled={!d?.path || q.isFetching || !!q.error} onClick={() => onPick(d.path)}>Chọn thư mục này</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function splitPath(p: string): { name: string; path: string }[] {
  const win = /^[A-Za-z]:\\/.test(p);
  const sep = win ? "\\" : "/";
  const parts = p.split(/[\\/]/).filter(Boolean);
  const out: { name: string; path: string }[] = [];
  let acc = win ? "" : "/";
  parts.forEach((part, i) => {
    acc = win ? (i === 0 ? `${part}\\` : `${acc}${acc.endsWith("\\") ? "" : sep}${part}`) : `${acc}${acc.endsWith("/") ? "" : "/"}${part}`;
    out.push({ name: part, path: acc });
  });
  if (!win) out.unshift({ name: "/", path: "/" });
  return out;
}
