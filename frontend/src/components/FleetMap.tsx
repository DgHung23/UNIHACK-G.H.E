/* eslint-disable @typescript-eslint/no-explicit-any */
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, Popup, Tooltip, useMap } from "react-leaflet";
import { Link } from "react-router-dom";
import { FRUIT_COLOR, STATUS_LABEL } from "../api/client";
import MapView, { validPosition } from "./maps/MapView";

function FleetMarkers({ batches }: { batches: any[] }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useEffect(() => {
    const update = () => setZoom(map.getZoom());
    map.on("zoomend", update);
    return () => { map.off("zoomend", update); };
  }, [map]);
  const groups = useMemo(() => {
    // Screen-space grouping separates nearby shipments as the user zooms in.
    const groups: any[][] = [];
    for (const batch of batches) {
      const point = map.project([batch.currentLat, batch.currentLon], zoom);
      const group = groups.find(items => point.distanceTo(map.project([items[0].currentLat, items[0].currentLon], zoom)) < 34);
      if (group) group.push(batch);
      else groups.push([batch]);
    }
    return groups;
  }, [batches, map, zoom]);
  return <>{groups.map(group => {
      const first = group[0], violation = group.some(b => b.hasViolation), multiple = group.length > 1;
      const center: [number, number] = [group.reduce((sum, b) => sum + b.currentLat, 0) / group.length, group.reduce((sum, b) => sum + b.currentLon, 0) / group.length];
      return <CircleMarker key={group.map(b => b.batchId).join(",")} center={center} radius={multiple ? 16 : 9}
        pathOptions={{ color: violation ? "#d6453b" : "#ffffff", weight: violation ? 3 : 2,
          fillColor: multiple ? "#0f6a7c" : FRUIT_COLOR[first.fruitId] || "#7f988f", fillOpacity: 0.95 }}>
        {multiple && <Tooltip permanent direction="center" className="map-count-label">{group.length}</Tooltip>}
        <Popup minWidth={220} maxWidth={280} autoPanPaddingTopLeft={[12, 74]} autoPanPaddingBottomRight={[60, 20]}>
          {multiple && <div className="mb-2 font-semibold">{group.length} lô trong khu vực này</div>}
          <div className="map-batch-list">
            {group.map(b => <div key={b.batchId} className="space-y-0.5 text-[13px]">
              <Link to={`/batches/${b.batchId}`} className="font-mono font-semibold text-cold-700">{b.batchId}</Link>
              <div>{b.productName} · {b.quantityKg} kg</div>
              <div className="text-ink-400">{STATUS_LABEL[b.status]} · {b.currentActorName}</div>
              {typeof b.latestRul?.rulDaysAtCurrent === "number" && <div>RUL {b.latestRul.rulDaysAtCurrent.toFixed(1)} ngày</div>}
            </div>)}
          </div>
        </Popup>
      </CircleMarker>;
    })}</>;
}

export default function FleetMap({ batches, height = 360 }: { batches: any[]; height?: number }) {
  const located = useMemo(() => batches.filter(b => validPosition(b.currentLat, b.currentLon)), [batches]);
  const points = useMemo(() => located.map(b => [b.currentLat, b.currentLon] as [number, number]), [located]);
  if (!points.length) return <div className="p-6 text-sm text-ink-400">Chưa có vị trí.</div>;
  return <MapView points={points} height={height} fitLabel="Về vị trí các lô"><FleetMarkers batches={located} /></MapView>;
}
