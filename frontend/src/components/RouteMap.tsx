/* eslint-disable @typescript-eslint/no-explicit-any */
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from "react-leaflet";
import { EVENT_LABEL, fmtTs } from "../api/client";

const EV_COLOR: Record<string, string> = { HARVEST: "#2f9a52", HANDOFF: "#0f6a7c", VIOLATION: "#d6453b", SOLD: "#2b4d42", INSPECTION: "#5057d8" };

export default function RouteMap({ readings, events }: { readings: any[]; events: any[] }) {
  const pts = readings.map((r) => [r.lat, r.lon] as [number, number]);
  const evs = events.filter((e) => e.lat != null && e.lon != null);
  const all = pts.length ? pts : evs.map((e) => [e.lat, e.lon] as [number, number]);
  if (!all.length) return <div className="p-6 text-sm text-slate-500">Chưa có dữ liệu vị trí.</div>;
  const lats = all.map((p) => p[0]), lons = all.map((p) => p[1]);
  const bounds: [[number, number], [number, number]] = [[Math.min(...lats) - 0.05, Math.min(...lons) - 0.05], [Math.max(...lats) + 0.05, Math.max(...lons) + 0.05]];
  const last = pts[pts.length - 1];
  return (
    <div className="h-[420px]">
      <MapContainer bounds={bounds} scrollWheelZoom={false}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <Polyline positions={pts} pathOptions={{ color: "#1a7f93", weight: 4, opacity: 0.85 }} />
        {evs.map((e) => (
          <CircleMarker key={e.eventId} center={[e.lat, e.lon]} radius={8} pathOptions={{ color: "#fff", weight: 2, fillColor: EV_COLOR[e.type] || "#64748b", fillOpacity: 1 }}>
            <Popup><b>{EVENT_LABEL[e.type] || e.type}</b><br />{fmtTs(e.ts)}<br />{e.actorName}{e.toActorName ? ` → ${e.toActorName}` : ""}</Popup>
          </CircleMarker>
        ))}
        {last && <CircleMarker center={last} radius={10} pathOptions={{ color: "#0d1c17", weight: 3, fillColor: "#fff", fillOpacity: 1 }}><Popup>Vị trí hiện tại</Popup></CircleMarker>}
      </MapContainer>
    </div>
  );
}
