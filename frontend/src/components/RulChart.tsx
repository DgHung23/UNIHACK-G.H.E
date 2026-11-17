/* eslint-disable @typescript-eslint/no-explicit-any */
import { Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";

const tick = (ts: string) => {
  const d = new Date(ts);
  return d.toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh", day: "2-digit", month: "2-digit", hour: "2-digit" });
};

export default function RulChart({ points, alertTempC, inspections = [], height = 340 }: { points: any[]; alertTempC?: number; inspections?: any[]; height?: number }) {
  const insByTs = new Map(inspections.filter((i) => i.rulImage != null).map((i) => [i.ts, i.rulImage]));
  const data = points.map((p) => ({ ...p, ci: [p.ciLowDays, p.ciHighDays], img: null as number | null }));
  // gắn điểm RUL-ảnh vào reading gần nhất
  for (const [ts, v] of insByTs) {
    let best = -1, bestD = Infinity;
    data.forEach((d, i) => { const dd = Math.abs(new Date(d.ts).getTime() - new Date(ts).getTime()); if (dd < bestD) { bestD = dd; best = i; } });
    if (best >= 0) data[best].img = v;
  }
  return (
    <div style={{ height }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="ts" tickFormatter={tick} minTickGap={40} tick={{ fontSize: 11 }} />
          <YAxis yAxisId="rul" tick={{ fontSize: 11 }} width={36} label={{ value: "ngày", angle: -90, position: "insideLeft", fontSize: 11 }} />
          <YAxis yAxisId="t" orientation="right" tick={{ fontSize: 11 }} width={36} label={{ value: "°C", angle: 90, position: "insideRight", fontSize: 11 }} />
          <Tooltip labelFormatter={(l) => new Date(l as string).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })}
            formatter={(v: any, n: any) => [Array.isArray(v) ? `${v[0]} – ${v[1]}` : v, n]} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area yAxisId="rul" dataKey="ci" name="Khoảng tin cậy (±15%)" fill="#a7f3d0" stroke="none" fillOpacity={0.5} isAnimationActive={false} />
          <Line yAxisId="rul" dataKey="rulDaysAtCurrent" name="RUL hiện tại" stroke="#059669" dot={false} strokeWidth={2} isAnimationActive={false} />
          <Line yAxisId="rul" dataKey="rulDaysAtOptimal" name="RUL nếu bảo quản chuẩn" stroke="#6366f1" dot={false} strokeDasharray="5 4" isAnimationActive={false} />
          <Line yAxisId="t" dataKey="tempC" name="Nhiệt độ" stroke="#f97316" dot={false} strokeWidth={1} isAnimationActive={false} />
          {inspections.length > 0 && <Scatter yAxisId="rul" dataKey="img" name="RUL từ ảnh" fill="#db2777" isAnimationActive={false} />}
          {alertTempC != null && <ReferenceLine yAxisId="t" y={alertTempC} stroke="#dc2626" strokeDasharray="4 4" label={{ value: `Ngưỡng ${alertTempC}°C`, fill: "#dc2626", fontSize: 11, position: "insideTopRight" }} />}
          <ReferenceLine yAxisId="rul" y={2} stroke="#f43f5e" strokeOpacity={0.4} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
