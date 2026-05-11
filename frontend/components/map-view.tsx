"use client";

import { useEffect, useMemo, useRef } from "react";
import type { Map as LeafletMap } from "leaflet";
import type { TripOutput } from "@/types/trip";

export function MapView({ trip }: { trip: TripOutput }) {
  const mapRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<LeafletMap | null>(null);
  const stops = useMemo(
    () =>
      trip.items
        .map((item) => ({
          name: item.place.name,
          coordinates: item.place.coordinates,
        }))
        .filter(
          (item): item is { name: string; coordinates: { lat: number; lng: number } } =>
            Boolean(item.coordinates),
        ),
    [trip.items],
  );

  useEffect(() => {
    if (!mapRef.current || stops.length === 0) return;
    let cancelled = false;

    void import("leaflet").then((leaflet) => {
      if (!mapRef.current || cancelled) return;
      mapInstanceRef.current?.remove();
      const map = leaflet
        .map(mapRef.current)
        .setView([stops[0].coordinates.lat, stops[0].coordinates.lng], 12);
      mapInstanceRef.current = map;
      leaflet.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap contributors",
      }).addTo(map);
      const stopIcon = leaflet.divIcon({
        className: "weekendgo-map-marker",
        html: '<span class="weekendgo-map-marker__pin"></span>',
        iconAnchor: [12, 24],
        popupAnchor: [0, -24],
      });
      stops.forEach((stop) => {
        leaflet
          .marker([stop.coordinates.lat, stop.coordinates.lng], { icon: stopIcon })
          .addTo(map)
          .bindPopup(stop.name);
      });
    });

    return () => {
      cancelled = true;
      mapInstanceRef.current?.remove();
      mapInstanceRef.current = null;
    };
  }, [stops]);

  if (stops.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-md border border-slate-200 bg-white text-sm text-slate-500">
        No map data
      </div>
    );
  }
  return <div ref={mapRef} className="h-72 overflow-hidden rounded-md border border-slate-200 bg-white" />;
}
