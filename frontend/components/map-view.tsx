"use client";

import { useEffect, useRef } from "react";
import type { TripOutput } from "@/types/trip";

export function MapView({ trip }: { trip: TripOutput }) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const coordinates = trip.items
    .map((item) => item.place.coordinates)
    .filter((item): item is { lat: number; lng: number } => Boolean(item));

  useEffect(() => {
    if (!mapRef.current || coordinates.length === 0) return;
    let cleanup = () => {};

    void import("leaflet").then((leaflet) => {
      if (!mapRef.current) return;
      const map = leaflet.map(mapRef.current).setView([coordinates[0].lat, coordinates[0].lng], 12);
      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);
      coordinates.forEach((point, index) => {
        leaflet.marker([point.lat, point.lng]).addTo(map).bindPopup(trip.items[index]?.place.name ?? "Stop");
      });
      cleanup = () => map.remove();
    });

    return () => cleanup();
  }, [coordinates, trip.items]);

  if (coordinates.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-md border border-slate-200 bg-white text-sm text-slate-500">
        No map data
      </div>
    );
  }
  return <div ref={mapRef} className="h-72 overflow-hidden rounded-md border border-slate-200 bg-white" />;
}
