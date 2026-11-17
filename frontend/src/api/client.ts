/* eslint-disable @typescript-eslint/no-explicit-any */
const TOKEN_KEY = "fruitchain_token";
const USER_KEY = "fruitchain_user";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function getStoredUser(): any | null {
  try { const s = localStorage.getItem(USER_KEY); return s ? JSON.parse(s) : null; } catch { return null; }
}
export function setSession(token: string | null, user?: any) {
  try {
    if (token) { localStorage.setItem(TOKEN_KEY, token); localStorage.setItem(USER_KEY, JSON.stringify(user)); }
    else { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }
  } catch { /* ignore */ }
}

export class ApiError extends Error {
  status: number;
  detail: any;
  constructor(status: number, detail: any) {
    super(typeof detail === "string" ? detail : detail?.message || JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token && opts.auth !== false) headers["Authorization"] = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  const res = await fetch(`/api${path}`, { method: opts.method || (body ? "POST" : "GET"), headers, body });
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    if (res.status === 401 && opts.auth !== false && !path.startsWith("/auth/")) {
      setSession(null);
      if (!location.pathname.startsWith("/login") && !location.pathname.startsWith("/trace")) location.href = "/login";
    }
    throw new ApiError(res.status, data?.detail ?? data);
  }
  return data as T;
}

export async function fetchBlobUrl(path: string): Promise<string> {
  const res = await fetch(`/api${path}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return URL.createObjectURL(await res.blob());
}

export const fmtTs = (ts?: string | null) => {
  if (!ts) return "—";
  const d = new Date(ts);
  return d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", hour12: false, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
};
export const short = (h?: string | null, n = 10) => (h ? `${h.slice(0, n)}…${h.slice(-4)}` : "—");

export const FRESH_COLORS: Record<string, string> = {
  FRESH: "#16a34a", GOOD: "#84cc16", NEAR_EXPIRY: "#f97316", EXPIRED: "#dc2626",
};
export const FRESH_LABEL: Record<string, string> = {
  FRESH: "Tươi", GOOD: "Tốt", NEAR_EXPIRY: "Sắp hết hạn", EXPIRED: "Hết hạn",
};
export const STATUS_LABEL: Record<string, string> = {
  HARVESTED: "Mới thu hoạch", IN_STORAGE: "Trong kho lạnh", IN_TRANSIT: "Đang vận chuyển",
  AT_DISTRIBUTOR: "Tại trung tâm phân phối", IN_STORE: "Tại cửa hàng", SOLD: "Đã bán",
};
export const ROLE_LABEL: Record<string, string> = {
  ADMIN: "Quản trị", FARMER: "Nông hộ", WAREHOUSE: "Kho lạnh", TRANSPORT: "Vận tải", DISTRIBUTOR: "Phân phối",
  RETAILER: "Cửa hàng", REGULATOR: "Kiểm định",
};
export const EVENT_LABEL: Record<string, string> = {
  HARVEST: "Thu hoạch", HANDOFF: "Chuyển giao", VIOLATION: "Vi phạm chuỗi lạnh", SOLD: "Đã bán", INSPECTION: "Kiểm tra ảnh",
};
