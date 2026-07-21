"use client";

import {
  Circle,
  LayersControl,
  MapContainer,
  Marker,
  Polygon,
  Polyline,
  Popup,
  ScaleControl,
  TileLayer,
  Tooltip,
} from "react-leaflet";
import L from "leaflet";
import type { LatLngExpression } from "leaflet";

type CommandLeafletMapProps = {
  stationId?: string | number | boolean | null;
  category?: string | number | boolean | null;
  onStationClick?: () => void;
};

const stationPosition: LatLngExpression = [13.045, 80.23];

const wardPolygon: LatLngExpression[] = [
  [13.092, 80.175],
  [13.106, 80.24],
  [13.076, 80.302],
  [13.013, 80.286],
  [12.998, 80.206],
  [13.038, 80.162],
];

const majorRoads: LatLngExpression[][] = [
  [
    [13.113, 80.178],
    [13.084, 80.205],
    [13.056, 80.233],
    [13.018, 80.261],
  ],
  [
    [13.017, 80.164],
    [13.036, 80.207],
    [13.058, 80.253],
    [13.079, 80.305],
  ],
  [
    [13.079, 80.151],
    [13.065, 80.199],
    [13.053, 80.247],
    [13.041, 80.306],
  ],
];

const poiMarkers = [
  { label: "School", type: "school", position: [13.058, 80.206] as LatLngExpression },
  { label: "Hospital", type: "hospital", position: [13.054, 80.248] as LatLngExpression },
  { label: "Hospital", type: "hospital", position: [13.02, 80.224] as LatLngExpression },
  { label: "Industrial POI", type: "factory", position: [13.025, 80.283] as LatLngExpression },
  { label: "Road work", type: "work", position: [13.038, 80.184] as LatLngExpression },
  { label: "Green space", type: "green", position: [13.004, 80.248] as LatLngExpression },
];

function iconFor(label: string, tone: string) {
  return L.divIcon({
    className: "",
    html: `<div style="
      display:grid;
      place-items:center;
      min-width:30px;
      height:26px;
      padding:0 6px;
      border-radius:8px;
      border:2px solid white;
      background:${tone};
      color:white;
      font-size:10px;
      font-weight:800;
      box-shadow:0 8px 20px rgba(15,23,42,.35);
    ">${label}</div>`,
    iconSize: [34, 30],
    iconAnchor: [17, 15],
  });
}

function stationIcon(category?: CommandLeafletMapProps["category"]) {
  const categoryText = String(category ?? "").toLowerCase();
  const color = categoryText.includes("satisfactory")
    ? "#84CC16"
    : categoryText.includes("good")
      ? "#16A34A"
      : categoryText.includes("poor")
        ? "#F97316"
        : "#0F766E";

  return L.divIcon({
    className: "",
    html: `<div style="
      display:grid;
      place-items:center;
      width:54px;
      height:54px;
      border-radius:999px;
      background:rgba(20,184,166,.22);
      border:1px solid rgba(94,234,212,.8);
    ">
      <div style="
        display:grid;
        place-items:center;
        width:34px;
        height:34px;
        border-radius:999px;
        border:4px solid white;
        background:${color};
        color:#0F172A;
        font-size:10px;
        font-weight:900;
        box-shadow:0 10px 28px rgba(0,0,0,.4);
      ">ST</div>
    </div>`,
    iconSize: [54, 54],
    iconAnchor: [27, 27],
  });
}

export default function CommandLeafletMap({
  stationId,
  category,
  onStationClick,
}: CommandLeafletMapProps) {
  return (
    <div className="relative h-[620px] overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700">
      <MapContainer
        center={stationPosition}
        zoom={12}
        minZoom={10}
        maxZoom={18}
        scrollWheelZoom
        className="h-full w-full"
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Satellite imagery">
            <TileLayer
              attribution="Tiles &copy; Esri, Maxar, Earthstar Geographics"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Street map">
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
          </LayersControl.BaseLayer>

          <LayersControl.Overlay checked name="Pilot ward boundary">
            <Polygon
              positions={wardPolygon}
              pathOptions={{
                color: "#A5B4FC",
                weight: 2,
                dashArray: "8 7",
                fillColor: "#312E81",
                fillOpacity: 0.08,
              }}
            />
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="Major roads">
            <>
              {majorRoads.map((road, index) => (
                <Polyline
                  key={index}
                  positions={road}
                  pathOptions={{ color: "#F97316", weight: 5, opacity: 0.82 }}
                />
              ))}
            </>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="Sentinel-5P NO2 signal">
            <Circle
              center={stationPosition}
              radius={3100}
              pathOptions={{
                color: "#F59E0B",
                fillColor: "#F59E0B",
                fillOpacity: 0.22,
                weight: 1,
              }}
            />
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="AQI station">
            <Marker
              position={stationPosition}
              icon={stationIcon(category)}
              eventHandlers={{
                click: () => onStationClick?.(),
              }}
            >
              <Popup>
                <strong>Station {String(stationId ?? "2586")}</strong>
                <br />
                CPCB category: {String(category ?? "Satisfactory")}
                <br />
                Click marker to open station drawer.
              </Popup>
            </Marker>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="Sensitive receptors and POIs">
            <>
              {poiMarkers.map((poi) => (
                <Marker
                  key={`${poi.label}-${String(poi.position)}`}
                  position={poi.position}
                  icon={iconFor(
                    poi.type === "hospital"
                      ? "H"
                      : poi.type === "school"
                        ? "SCH"
                        : poi.type === "factory"
                          ? "IND"
                          : poi.type === "work"
                            ? "WRK"
                            : "GRN",
                    poi.type === "hospital"
                      ? "#DC2626"
                      : poi.type === "school"
                        ? "#2563EB"
                        : poi.type === "factory"
                          ? "#7C2D12"
                          : poi.type === "work"
                            ? "#D97706"
                            : "#15803D",
                  )}
                >
                  <Tooltip direction="top">{poi.label}</Tooltip>
                </Marker>
              ))}
            </>
          </LayersControl.Overlay>

          <LayersControl.Overlay checked name="Wind direction">
            <Polyline
              positions={[
                [13.045, 80.29],
                [13.045, 80.235],
              ]}
              pathOptions={{ color: "#22D3EE", weight: 4, opacity: 0.95 }}
            />
          </LayersControl.Overlay>
        </LayersControl>
        <ScaleControl position="bottomleft" />
      </MapContainer>

      <div className="pointer-events-none absolute left-4 top-4 rounded-xl border border-slate-200 bg-white/95 p-3 shadow dark:border-slate-700 dark:bg-slate-950/95">
        <div className="text-xs font-bold uppercase tracking-[0.16em] text-teal-700 dark:text-teal-300">
          Leaflet satellite command layer
        </div>
        <div className="mt-1 text-[11px] font-medium text-slate-600 dark:text-slate-300">
          Chennai pilot | 13.045 N, 80.230 E
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-4 right-4 rounded-xl border border-teal-200 bg-white/95 px-4 py-2 text-sm font-semibold text-teal-900 shadow dark:border-teal-700 dark:bg-slate-950/95 dark:text-teal-200">
        Satellite base | NO2 overlay | Road exposure | Sensitive receptors
      </div>
    </div>
  );
}
