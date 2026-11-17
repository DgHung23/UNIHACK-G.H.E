/* eslint-disable @typescript-eslint/no-explicit-any */
import { useMemo } from "react";
import { CircleMarker, Polyline, Popup } from "react-leaflet";
import { EVENT_LABEL, fmtTs } from "../api/client";
import MapView, { validPosition } from "./maps/MapView";

const EV_COLOR: Record<string, string> = { HARVEST: "#2f9a52", HANDOFF: "#0f6a7c", VIOLATION: "#d6453b", SOLD: "#2b4d42", INSPECTION: "#5057d8" };

export default function RouteMap({ readings, events }: { readings: any[]; events: any[] }) {
  const { pts, evs, all } = useMemo(() => {
    const pts = readings.filter(r => validPosition(r.lat, r.lon))
      .map(r => [r.lat, r.lon] as [number, number])
      .filter((point, i, positions) => i === 0 || point[0] !== positions[i - 1][0] || point[1] !== positions[i - 1][1]);
    const evs = events.filter(e => validPosition(e.lat, e.lon));
    return { pts, evs, all: [...pts, ...evs.map(e => [e.lat, e.lon] as [number, number])] };
  }, [readings, events]);
  if (!all.length) return <div className="p-6 text-sm text-ink-400">Chưa có dữ liệu vị trí.</div>;
  const last = pts[pts.length - 1];
  return <MapView points={all}>
    <Polyline positions={pts} pathOptions={{ color: "#ffffff", weight: 7, opacity: 0.85 }} interactive={false} />
    <Polyline positions={pts} pathOptions={{ color: "#1a7f93", weight: 4, opacity: 0.95 }} />
    {evs.map(e => <CircleMarker key={e.eventId} center={[e.lat, e.lon]} radius={8}
      pathOptions={{ color: "#fff", weight: 2, fillColor: EV_COLOR[e.type] || "#64748b", fillOpacity: 1 }}>
      <Popup autoPanPaddingTopLeft={[12, 74]}><b>{EVENT_LABEL[e.type] || e.type}</b><br />{fmtTs(e.ts)}<br />{e.actorName}{e.toActorName ? ` → ${e.toActorName}` : ""}</Popup>
    </CircleMarker>)}
    {last && <CircleMarker center={last} radius={10} pathOptions={{ color: "#0d1c17", weight: 3, fillColor: "#fff", fillOpacity: 1 }}><Popup autoPanPaddingTopLeft={[12, 74]}>Vị trí hiện tại</Popup></CircleMarker>}
  </MapView>;
}
