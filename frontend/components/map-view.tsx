"use client";

import { useEffect, useState } from "react";
import type { Place } from "@/types/trip";

interface MapViewProps {
  places: Place[];
  className?: string;
}

const CHINA_CENTER = { lat: 35.8617, lng: 104.1954 };

function MapInner({ places, className }: MapViewProps) {
  const [map, setMap] = useState<L.Map | null>(null);
  const [markers, setMarkers] = useState<L.Marker[]>([]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    import("leaflet").then((L) => {
      if (!map) {
        const mapInstance = L.map("map-container", {
          center: [CHINA_CENTER.lat, CHINA_CENTER.lng],
          zoom: 5,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        }).addTo(mapInstance);

        setMap(mapInstance);
      }
    });
  }, []);

  useEffect(() => {
    if (!map || typeof window === "undefined") return;

    import("leaflet").then((L) => {
      markers.forEach((m) => m.remove());

      const placesWithCoords = places.filter(
        (p) => p.coordinates?.lat && p.coordinates?.lng
      );

      if (placesWithCoords.length === 0) {
        map.setView([CHINA_CENTER.lat, CHINA_CENTER.lng], 5);
        setMarkers([]);
        return;
      }

      const newMarkers: L.Marker[] = [];
      const bounds: L.LatLngBoundsExpression = [];

      placesWithCoords.forEach((place) => {
        if (place.coordinates) {
          const latLng: L.LatLngExpression = [
            place.coordinates.lat,
            place.coordinates.lng,
          ];
          bounds.push(latLng);

          const marker = L.marker(latLng)
            .bindPopup(`<strong>${place.name}</strong>${place.address ? `<br/><small>${place.address}</small>` : ""}`)
            .addTo(map);

          newMarkers.push(marker);
        }
      });

      setMarkers(newMarkers);

      if (bounds.length > 0) {
        map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50] });
      }
    });
  }, [map, places]);

  useEffect(() => {
    return () => {
      if (map) {
        map.remove();
      }
    };
  }, [map]);

  return (
    <div
      id="map-container"
      className={`w-full h-[400px] rounded-lg border border-border ${className || ""}`}
    />
  );
}

export function MapView({ places, className }: MapViewProps) {
  const [mounted, setMounted] = useState(false);

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

  const placesWithCoords = places.filter(
    (p) => p.coordinates?.lat && p.coordinates?.lng
  );

  if (placesWithCoords.length === 0) {
    return (
      <div
        className={`w-full h-[200px] rounded-lg border border-border bg-muted/20 flex items-center justify-center ${className || ""}`}
      >
        <div className="text-muted text-sm">暂无地点坐标数据</div>
      </div>
    );
  }

  return <MapInner places={places} className={className} />;
}