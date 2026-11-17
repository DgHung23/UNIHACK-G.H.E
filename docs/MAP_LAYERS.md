# Map layers

Both shipment maps share `frontend/src/components/maps/MapView.tsx`. No API key is required by the current public endpoints.

- **Bản đồ:** NARENCA's Vietnam base map (`vietnam_2026`) and Vietnamese labels (`vietnam_label_2026`), served as transparent WMS tiles over a neutral background. Coverage is Vietnam; this is not a global street map.
- **Vệ tinh:** Esri World Imagery with the same NARENCA label overlay. Imagery contains no place labels; Vietnamese labels, including QĐ. Hoàng Sa and QĐ. Trường Sa, come from the provider's map data.

Provider references:

- Vietnam map: https://cosodulieu.bando.com.vn/
- Public WMS capabilities: https://cache.bando.com.vn/service?SERVICE=WMS&REQUEST=GetCapabilities
- Imagery metadata and attribution: https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer?f=pjson
- Leaflet interactions: https://leafletjs.com/reference-1.9.4.html

WMS uses version 1.1.1 and Leaflet's EPSG:3857 coordinates. Provider credits remain visible in both modes. Native WMS requests stop at zoom 16 and are enlarged at higher zoom levels; imagery requests stop at zoom 19. Detail and availability depend on the upstream service. Confirm usage terms and capacity with the providers before a larger deployment. Failed tiles show a retry action and do not change to a different label source.

Controls support wheel, pinch, double-click, keyboard, half-step zoom buttons, fitting shipment positions, viewing Vietnam including the archipelagos, and fullscreen (Escape exits). Reduced-motion preferences disable animated fit actions. Nearby shipments share a marker with a scrollable list; groups separate as the user zooms in. Vietnamese labels receive a light halo in satellite mode for contrast.
