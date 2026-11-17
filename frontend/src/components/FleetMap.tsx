/* eslint-disable @typescript-eslint/no-explicit-any */
import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { Link } from "react-router-dom";
import { FRUIT_COLOR, STATUS_LABEL } from "../api/client";

/** Bản đồ vị trí hiện tại của các lô đang lưu thông (màu theo loại quả, viền đỏ nếu có vi phạm). */
export default function FleetMap({ batches, height = 360 }: { batches: any[]; height?: number }) {
  const pts = batches.filter((b) => b.currentLat != null && b.currentLon != null);
  if (!pts.length) return <div className="p-6 text-sm text-ink-400">Chưa có vị trí.</div>;
  const lats = pts.map((b) => b.currentLat), lons = pts.map((b) => b.currentLon);
  const bounds: [[number, number], [number, number]] = [[Math.min(...lats) - 0.3, Math.min(...lons) - 0.3], [Math.max(...lats) + 0.3, Math.max(...lons) + 0.3]];
  return (
    <div style={{ height }}>
      <MapContainer bounds={bounds} scrollWheelZoom={false}>
        <TileLayer attribution="&copy; OpenStreetMap &copy; CARTO" url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png" />
        {pts.map((b) => (
          <CircleMarker key={b.batchId} center={[b.currentLat, b.currentLon]} radius={b.status === "IN_TRANSIT" ? 9 : 7}
            pathOptions={{ color: b.hasViolation ? "#d6453b" : "#ffffff", weight: b.hasViolation ? 3 : 2, fillColor: FRUIT_COLOR[b.fruitId] || "#7f988f", fillOpacity: 0.95 }}>
            <Popup>
              <div className="space-y-0.5 text-[13px]">
                <Link to={`/batches/${b.batchId}`} className="font-mono font-semibold text-cold-700">{b.batchId}</Link>
                <div>{b.productName} · {b.quantityKg} kg</div>
                <div className="text-ink-400">{STATUS_LABEL[b.status]} · {b.currentActorName}</div>
                <div>RUL {b.latestRul?.rulDaysAtCurrent?.toFixed(1)} ngày</div>
              </div>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
