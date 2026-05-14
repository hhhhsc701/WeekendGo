"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Place } from "@/types/trip";

interface MapViewProps {
  places: Place[];
  className?: string;
}

const CHINA_CENTER = { lat: 35.8617, lng: 104.1954 };
const X_PI = (Math.PI * 3000.0) / 180.0;
const A = 6378245.0;
const EE = 0.00669342162296594323;

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function hasValidCoordinates(place: Place): boolean {
  return isFiniteNumber(place.coordinates?.lat) && isFiniteNumber(place.coordinates?.lng);
}

function isInChina(lat: number, lng: number): boolean {
  return lng >= 72.004 && lng <= 137.8347 && lat >= 0.8293 && lat <= 55.8271;
}

function transformLat(x: number, y: number): number {
  let ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
  ret += ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0) / 3.0;
  ret += ((20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin((y / 3.0) * Math.PI)) * 2.0) / 3.0;
  ret += ((160.0 * Math.sin((y / 12.0) * Math.PI) + 320 * Math.sin((y * Math.PI) / 30.0)) * 2.0) / 3.0;
  return ret;
}

function transformLng(x: number, y: number): number {
  let ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
  ret += ((20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0) / 3.0;
  ret += ((20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin((x / 3.0) * Math.PI)) * 2.0) / 3.0;
  ret += ((150.0 * Math.sin((x / 12.0) * Math.PI) + 300.0 * Math.sin((x / 30.0) * Math.PI)) * 2.0) / 3.0;
  return ret;
}

function gcj02ToWgs84(lat: number, lng: number): [number, number] {
  if (!isInChina(lat, lng)) return [lat, lng];

  let dLat = transformLat(lng - 105.0, lat - 35.0);
  let dLng = transformLng(lng - 105.0, lat - 35.0);
  const radLat = (lat / 180.0) * Math.PI;
  let magic = Math.sin(radLat);
  magic = 1 - EE * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / (((A * (1 - EE)) / (magic * sqrtMagic)) * Math.PI);
  dLng = (dLng * 180.0) / ((A / sqrtMagic) * Math.cos(radLat) * Math.PI);
  return [lat * 2 - (lat + dLat), lng * 2 - (lng + dLng)];
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

interface MapPoint {
  index: number;
  latLng: [number, number];
  place: Place;
}

interface MarkerPoint {
  latLng: [number, number];
  points: MapPoint[];
}

function toMapPoint(place: Place, index: number): MapPoint | null {
  const coordinates = place.coordinates;
  if (
    !isFiniteNumber(coordinates?.lat) ||
    !isFiniteNumber(coordinates?.lng)
  ) {
    return null;
  }

  const { lat, lng } = coordinates;
  return { index, latLng: gcj02ToWgs84(lat, lng), place };
}

function angleBetweenPoints(from: L.Point, to: L.Point): number {
  return (Math.atan2(to.y - from.y, to.x - from.x) * 180) / Math.PI;
}

function isHotelPlace(place: Place): boolean {
  const text = `${place.name} ${place.category || ""}`.toLowerCase();
  return text.includes("酒店") || text.includes("住宿") || text.includes("hotel");
}

function isTransportPlace(place: Place): boolean {
  return place.category === "departure" || place.category === "transport";
}

function groupMarkerPoints(points: MapPoint[]): MarkerPoint[] {
  const grouped = new Map<string, MarkerPoint>();

  points.forEach((point) => {
    const key = `${point.latLng[0].toFixed(6)},${point.latLng[1].toFixed(6)}`;
    const existing = grouped.get(key);
    if (existing) {
      existing.points.push(point);
    } else {
      grouped.set(key, { latLng: point.latLng, points: [point] });
    }
  });

  return Array.from(grouped.values());
}

function MapInner({ places, className }: MapViewProps) {
  const [showRoute, setShowRoute] = useState(true);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Layer[]>([]);
  const routeLayerRef = useRef<L.Layer | null>(null);
  const mapPoints = useMemo(
    () => places.map((place, index) => toMapPoint(place, index)).filter((point) => point !== null),
    [places]
  );
  const markerPoints = useMemo(() => groupMarkerPoints(mapPoints), [mapPoints]);

  useEffect(() => {
    let cancelled = false;

    import("leaflet").then((L) => {
      if (cancelled || !containerRef.current || mapRef.current) return;

      const map = L.map(containerRef.current, {
        center: [CHINA_CENTER.lat, CHINA_CENTER.lng],
        zoom: 5,
        scrollWheelZoom: true,
      });

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map);

      mapRef.current = map;
      window.setTimeout(() => map.invalidateSize(), 0);
    });

    return () => {
      cancelled = true;
      routeLayerRef.current?.remove();
      routeLayerRef.current = null;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    import("leaflet").then((L) => {
      if (cancelled || !mapRef.current) return;

      const map = mapRef.current;
      routeLayerRef.current?.remove();
      routeLayerRef.current = null;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];

      if (mapPoints.length === 0) {
        map.setView([CHINA_CENTER.lat, CHINA_CENTER.lng], 5);
        return;
      }

      const bounds: L.LatLngExpression[] = [];
      if (showRoute && mapPoints.length > 1) {
        const routeGroup = L.layerGroup();
        L.polyline(
          mapPoints.map(({ latLng }) => latLng),
          {
            color: "#2563eb",
            weight: 3,
            opacity: 0.72,
            dashArray: "8 8",
            lineCap: "round",
            lineJoin: "round",
          }
        ).addTo(routeGroup);

        for (let index = 0; index < mapPoints.length - 1; index += 1) {
          const from = L.latLng(mapPoints[index].latLng);
          const to = L.latLng(mapPoints[index + 1].latLng);
          const fromPoint = map.latLngToLayerPoint(from);
          const toPoint = map.latLngToLayerPoint(to);
          const middle = L.latLng((from.lat + to.lat) / 2, (from.lng + to.lng) / 2);
          const angle = angleBetweenPoints(fromPoint, toPoint);

          L.marker(middle, {
            interactive: false,
            icon: L.divIcon({
              className: "",
              html: `<div style="transform: rotate(${angle}deg); color: #2563eb; font-size: 18px; line-height: 18px; text-shadow: 0 1px 2px rgba(255,255,255,0.95);">➤</div>`,
              iconSize: [18, 18],
              iconAnchor: [9, 9],
            }),
          }).addTo(routeGroup);
        }

        routeGroup.addTo(map);
        routeLayerRef.current = routeGroup;
      }

      markersRef.current = markerPoints.map(({ latLng, points }) => {
        bounds.push(latLng);
        const hasHotel = points.some(({ place }) => isHotelPlace(place));
        const hasTransportPoint = points.some(({ place }) => isTransportPlace(place));
        const color = hasHotel ? "#047857" : hasTransportPoint ? "#dc2626" : "#2563eb";
        const fillColor = hasHotel ? "#10b981" : hasTransportPoint ? "#ef4444" : "#3b82f6";
        const popup = points
          .map(({ index, place }) => {
            const address = place.address ? `<br/><small>${escapeHtml(place.address)}</small>` : "";
            return `<div><strong>${index + 1}. ${escapeHtml(place.name)}</strong>${address}</div>`;
          })
          .join('<div style="height: 6px"></div>');
        return L.circleMarker(latLng, {
          radius: hasHotel || hasTransportPoint ? 8 : 7,
          color,
          weight: 2,
          fillColor,
          fillOpacity: 0.85,
        })
          .bindPopup(popup)
          .addTo(map);
      });

      map.fitBounds(L.latLngBounds(bounds), {
        padding: [40, 40],
        maxZoom: 14,
      });
      window.setTimeout(() => map.invalidateSize(), 0);
    });

    return () => {
      cancelled = true;
    };
  }, [mapPoints, markerPoints, showRoute]);

  return (
    <div className={`relative h-[400px] w-full rounded-lg border border-border overflow-hidden ${className || ""}`}>
      <div ref={containerRef} className="h-full w-full" />
      {mapPoints.length > 1 && (
        <label className="absolute right-3 top-3 z-[1000] inline-flex items-center gap-2 rounded-md border border-border bg-background/95 px-3 py-2 text-xs font-medium text-foreground shadow-sm">
          <input
            type="checkbox"
            checked={showRoute}
            onChange={(event) => setShowRoute(event.target.checked)}
            className="h-4 w-4 accent-primary"
          />
          路线连线
        </label>
      )}
    </div>
  );
}

export function MapView({ places, className }: MapViewProps) {
  const [mounted, setMounted] = useState(false);
  const placesWithCoords = places.filter(hasValidCoordinates);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div
        className={`h-[400px] w-full rounded-lg border border-border bg-muted/20 flex items-center justify-center ${className || ""}`}
      >
        <div className="text-muted text-sm">地图加载中...</div>
      </div>
    );
  }

  if (placesWithCoords.length === 0) {
    return (
      <div
        className={`h-[200px] w-full rounded-lg border border-border bg-muted/20 flex items-center justify-center ${className || ""}`}
      >
        <div className="text-muted text-sm">暂无地点坐标数据</div>
      </div>
    );
  }

  return <MapInner places={placesWithCoords} className={className} />;
}
