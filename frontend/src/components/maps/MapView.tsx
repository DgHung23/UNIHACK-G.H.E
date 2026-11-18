import { useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { latLngBounds, DomEvent, type LatLngTuple } from "leaflet";
import { MapContainer, Pane, ScaleControl, TileLayer, WMSTileLayer, useMap } from "react-leaflet";
import { LocateFixed, Map as MapIcon, Maximize2, Minimize2, Minus, Plus, Satellite, Scan, RotateCw } from "lucide-react";

// Public map services: NARENCA Vietnam base/labels and Esri World Imagery.
const VIETNAM_WMS = "https://cache.bando.com.vn/service";
const IMAGERY = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const VIETNAM_BOUNDS: [LatLngTuple, LatLngTuple] = [[7, 101], [24, 119]];
const VIETNAM_CREDIT = '&copy; <a href="https://cosodulieu.bando.com.vn/" target="_blank" rel="noopener noreferrer">NARENCA</a>';
const IMAGERY_CREDIT = 'Esri, Vantor, Earthstar Geographics, GIS User Community';

export function validPosition(lat: unknown, lon: unknown): boolean {
  return typeof lat === "number" && typeof lon === "number" && Number.isFinite(lat) && Number.isFinite(lon)
    && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
}

function Controls({ points, fitLabel, shell, fullscreen, toggleFullscreen, mode, setMode }: {
  points: LatLngTuple[]; fitLabel: string; shell: RefObject<HTMLDivElement>;
  fullscreen: boolean; toggleFullscreen: () => void;
  mode: "street" | "satellite"; setMode: (mode: "street" | "satellite") => void;
}) {
  const map = useMap();
  const toolbar = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(map.getZoom());
  useEffect(() => {
    if (toolbar.current) {
      DomEvent.disableClickPropagation(toolbar.current);
      DomEvent.disableScrollPropagation(toolbar.current);
    }
    const update = () => setZoom(map.getZoom());
    map.on("zoomend", update);
    const resize = new ResizeObserver(() => map.invalidateSize({ pan: false }));
    if (shell.current) resize.observe(shell.current);
    return () => { map.off("zoomend", update); resize.disconnect(); };
  }, [map, shell]);
  const fit = (country = false) => {
    const bounds = country ? latLngBounds(VIETNAM_BOUNDS) : latLngBounds(points);
    map.fitBounds(bounds, { paddingTopLeft: [28, 74], paddingBottomRight: [28, 40], maxZoom: country ? 7 : 13,
      animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches, duration: 0.7 });
  };
  return <div ref={toolbar} className="map-toolbar">
    <div className="map-layer-switch" role="group" aria-label="Kiểu bản đồ">
      <button type="button" aria-pressed={mode === "street"} onClick={() => setMode("street")}><MapIcon size={15} />Bản đồ</button>
      <button type="button" aria-pressed={mode === "satellite"} onClick={() => setMode("satellite")}><Satellite size={15} />Vệ tinh</button>
    </div>
    <div className="map-actions">
      <button type="button" title={fullscreen ? "Thoát toàn màn hình" : "Toàn màn hình"} aria-label={fullscreen ? "Thoát toàn màn hình" : "Toàn màn hình"} onClick={toggleFullscreen}>{fullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}</button>
      <button type="button" title={fitLabel} aria-label={fitLabel} onClick={() => fit()}><LocateFixed size={18} /></button>
      <button type="button" title="Toàn cảnh Việt Nam" aria-label="Toàn cảnh Việt Nam" onClick={() => fit(true)}><Scan size={18} /></button>
      <span className="map-control-divider" />
      <button type="button" title="Phóng to" aria-label="Phóng to" disabled={zoom >= map.getMaxZoom()} onClick={() => map.zoomIn()}><Plus size={18} /></button>
      <button type="button" title="Thu nhỏ" aria-label="Thu nhỏ" disabled={zoom <= map.getMinZoom()} onClick={() => map.zoomOut()}><Minus size={18} /></button>
    </div>
  </div>;
}

export default function MapView({ points, children, height = 420, fitLabel = "Về tuyến đường" }: {
  points: LatLngTuple[]; children: ReactNode; height?: number; fitLabel?: string;
}) {
  const shell = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"street" | "satellite">("street");
  const [fullscreen, setFullscreen] = useState(false);
  const [fallbackFullscreen, setFallbackFullscreen] = useState(false);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const bounds = useMemo(() => latLngBounds(points), [points]);
  useEffect(() => { setFailed(false); }, [mode]);
  useEffect(() => {
    const sync = () => setFullscreen(document.fullscreenElement === shell.current);
    document.addEventListener("fullscreenchange", sync);
    return () => document.removeEventListener("fullscreenchange", sync);
  }, []);
  useEffect(() => {
    if (!fallbackFullscreen) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setFallbackFullscreen(false); setFullscreen(false); } };
    document.addEventListener("keydown", escape);
    return () => { document.body.style.overflow = previous; document.removeEventListener("keydown", escape); };
  }, [fallbackFullscreen]);
  const toggleFullscreen = async () => {
    if (fallbackFullscreen) { setFallbackFullscreen(false); setFullscreen(false); return; }
    if (document.fullscreenElement === shell.current) { await document.exitFullscreen(); return; }
    try { await shell.current!.requestFullscreen(); }
    catch { setFallbackFullscreen(true); setFullscreen(true); }
  };
  const tileEvents = useMemo(() => ({ tileerror: () => setFailed(true) }), []);
  return <div ref={shell} className={`map-shell map-${mode}${fallbackFullscreen ? " map-fullscreen" : ""}`} style={{ height }} role="region" aria-label="Bản đồ vận chuyển">
    <MapContainer bounds={bounds} boundsOptions={{ paddingTopLeft: [28, 74], paddingBottomRight: [28, 40], maxZoom: 13 }}
      minZoom={4} maxZoom={19} zoomControl={false} scrollWheelZoom zoomSnap={0.25} zoomDelta={0.5}
      wheelDebounceTime={40} wheelPxPerZoomLevel={120} inertia inertiaDeceleration={1800}
      touchZoom bounceAtZoomLimits={false} preferCanvas>
      {mode === "satellite" && <TileLayer key={`imagery-${attempt}`} url={IMAGERY} attribution={IMAGERY_CREDIT} maxNativeZoom={19} keepBuffer={3} eventHandlers={tileEvents} />}
      {mode === "street" && <WMSTileLayer key={`base-${attempt}`} url={VIETNAM_WMS} layers="vietnam_2026" version="1.1.1" format="image/png" transparent maxNativeZoom={16} maxZoom={19} keepBuffer={3} eventHandlers={tileEvents} />}
      <Pane name="vietnam-labels" style={{ zIndex: 350, pointerEvents: "none" }}>
        <WMSTileLayer key={`labels-${mode}-${attempt}`} url={VIETNAM_WMS} layers="vietnam_label_2026" version="1.1.1" format="image/png" transparent attribution={VIETNAM_CREDIT} maxNativeZoom={16} maxZoom={19} keepBuffer={3} eventHandlers={tileEvents} />
      </Pane>
      {children}
      <ScaleControl position="bottomleft" imperial={false} />
      <Controls points={points} fitLabel={fitLabel} shell={shell} fullscreen={fullscreen} toggleFullscreen={toggleFullscreen} mode={mode} setMode={setMode} />
    </MapContainer>
    {failed && <div className="map-load-error" role="status">Một phần bản đồ chưa tải được.<button type="button" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}><RotateCw size={13} />Thử lại</button></div>}
    <div className="map-gesture-hint">Cuộn để thu phóng · Kéo để di chuyển</div>
  </div>;
}
