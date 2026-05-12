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

function toMapPoint(place: Place): { latLng: [number, number]; place: Place } | null {
  const coordinates = place.coordinates;
  if (
    !isFiniteNumber(coordinates?.lat) ||
    !isFiniteNumber(coordinates?.lng)
  ) {
    return null;
  }

  const { lat, lng } = coordinates;
  return { latLng: gcj02ToWgs84(lat, lng), place };
}

function MapInner({ places, className }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<L.Layer[]>([]);
  const mapPoints = useMemo(() => places.map(toMapPoint).filter((point) => point !== null), [places]);

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
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];

      if (mapPoints.length === 0) {
        map.setView([CHINA_CENTER.lat, CHINA_CENTER.lng], 5);
        return;
      }

      const bounds: L.LatLngExpression[] = [];
      markersRef.current = mapPoints.map(({ latLng, place }) => {
        bounds.push(latLng);
        const address = place.address ? `<br/><small>${escapeHtml(place.address)}</small>` : "";
        const isTransportPoint = place.category === "departure" || place.category === "transport";
        const color = isTransportPoint ? "#dc2626" : "#2563eb";
        const fillColor = isTransportPoint ? "#ef4444" : "#3b82f6";
        return L.circleMarker(latLng, {
          radius: isTransportPoint ? 8 : 7,
          color,
          weight: 2,
          fillColor,
          fillOpacity: 0.85,
        })
          .bindPopup(`<strong>${escapeHtml(place.name)}</strong>${address}`)
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
  }, [mapPoints]);

  return (
    <div
      ref={containerRef}
      className={`w-full h-[400px] rounded-lg border border-border overflow-hidden ${className || ""}`}
    />
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
        className={`w-full h-[400px] rounded-lg border border-border bg-muted/20 flex items-center justify-center ${className || ""}`}
      >
        <div className="text-muted text-sm">地图加载中...</div>
      </div>
    );
  }

  if (placesWithCoords.length === 0) {
    return (
      <div
        className={`w-full h-[200px] rounded-lg border border-border bg-muted/20 flex items-center justify-center ${className || ""}`}
      >
        <div className="text-muted text-sm">暂无地点坐标数据</div>
      </div>
    );
  }

  return <MapInner places={placesWithCoords} className={className} />;
}
