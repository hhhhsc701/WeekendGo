"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, MapPin, Calendar, Clock, DollarSign, Cloud, History, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TimelineView } from "@/components/timeline-view";
import { MapView } from "@/components/map-view";
import { getTrip, ApiError } from "@/lib/api";
import { getCityCoordinates } from "@/lib/city-coordinates";
import type { Coordinates, Place, TripOutput } from "@/types/trip";

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function hasWeatherSummary(summary?: string | null): boolean {
  if (!summary) return false;
  const normalized = summary.trim();
  if (!normalized) return false;
  return !["不可用", "暂不可用", "无法获取", "unknown", "unavailable"].some((text) =>
    normalized.toLowerCase().includes(text)
  );
}

function hasCoordinates(item: TripOutput["items"][number]): boolean {
  const coordinates = item.place.coordinates;
  return (
    typeof coordinates?.lat === "number" &&
    Number.isFinite(coordinates.lat) &&
    typeof coordinates?.lng === "number" &&
    Number.isFinite(coordinates.lng)
  );
}

function hasValidCoordinates(coordinates?: Coordinates | null): coordinates is Coordinates {
  return (
    typeof coordinates?.lat === "number" &&
    Number.isFinite(coordinates.lat) &&
    typeof coordinates?.lng === "number" &&
    Number.isFinite(coordinates.lng)
  );
}

function addUniquePlace(places: Place[], seen: Set<string>, place: Place): void {
  if (!hasValidCoordinates(place.coordinates)) return;

  const key = [
    place.name.trim().toLowerCase(),
    place.coordinates.lat.toFixed(6),
    place.coordinates.lng.toFixed(6),
  ].join("|");
  if (seen.has(key)) return;

  seen.add(key);
  places.push(place);
}

function distanceMeters(a: Coordinates, b: Coordinates): number {
  const earthRadiusMeters = 6371000;
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const dLat = toRadians(b.lat - a.lat);
  const dLng = toRadians(b.lng - a.lng);
  const lat1 = toRadians(a.lat);
  const lat2 = toRadians(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * earthRadiusMeters * Math.asin(Math.sqrt(h));
}

function isInDestinationCity(place: Place, destinationCoordinates: Coordinates | null): boolean {
  if (!destinationCoordinates || !hasValidCoordinates(place.coordinates)) return true;
  return distanceMeters(place.coordinates, destinationCoordinates) <= 150000;
}

function buildMapPlaces(trip: TripOutput): Place[] {
  const places: Place[] = [];
  const seen = new Set<string>();
  const destinationCoordinates = getCityCoordinates(trip.input.city);

  trip.items.forEach((item) => {
    if (hasCoordinates(item) && isInDestinationCity(item.place, destinationCoordinates)) {
      addUniquePlace(places, seen, item.place);
    }
  });

  return places;
}

function Skeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-8 bg-muted/30 rounded w-1/3" />
      <div className="h-4 bg-muted/30 rounded w-1/2" />
      <div className="h-4 bg-muted/30 rounded w-1/4" />
      <div className="mt-8 space-y-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-muted/20 rounded-lg p-4 space-y-3">
            <div className="h-4 bg-muted/30 rounded w-1/4" />
            <div className="h-5 bg-muted/30 rounded w-1/2" />
            <div className="h-4 bg-muted/30 rounded w-1/3" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ItineraryDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [trip, setTrip] = useState<TripOutput | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTrip = async () => {
      setLoading(true);
      setError(null);

      try {
        const data = await getTrip(id);
        setTrip(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setError("行程不存在或已被删除");
        } else {
          setError(err instanceof Error ? err.message : "加载行程失败");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchTrip();
  }, [id]);

  if (loading) {
    return (
      <main className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <Button
            variant="ghost"
            onClick={() => router.push("/")}
            className="mb-6"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回首页
          </Button>
          <Skeleton />
        </div>
      </main>
    );
  }

  if (error || !trip) {
    return (
      <main className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <Button
            variant="ghost"
            onClick={() => router.push("/")}
            className="mb-6"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回首页
          </Button>

          <div className="text-center py-12">
            <AlertCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
            <h2 className="text-xl font-semibold text-foreground mb-2">
              加载失败
            </h2>
            <p className="text-muted mb-6">{error || "行程不存在"}</p>
            <div className="flex gap-4 justify-center">
              <Button onClick={() => router.push("/")}>
                返回首页
              </Button>
              <Button variant="outline" onClick={() => router.push("/history")}>
                <History className="w-4 h-4 mr-2" />
                查看历史
              </Button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  const weatherSummary = trip.weather_summary?.summary?.trim();
  const placesWithCoords = buildMapPlaces(trip);

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <Button
            variant="ghost"
            onClick={() => router.push("/")}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回首页
          </Button>

          <Button
            variant="outline"
            onClick={() => router.push("/history")}
          >
            <History className="w-4 h-4 mr-2" />
            历史行程
          </Button>
        </div>

        <header className="mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-foreground mb-4">
            {trip.title}
          </h1>

          <div className="flex flex-wrap gap-4 text-sm text-muted">
            <div className="flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              <span>{trip.input.city}</span>
            </div>

            <div className="flex items-center gap-1">
              <Calendar className="w-4 h-4" />
              <span>{formatDate(trip.input.date)}</span>
            </div>

            <div className="flex items-center gap-1">
              <Clock className="w-4 h-4" />
              <span>{trip.input.days}天</span>
            </div>

            {trip.total_budget && (
              <div className="flex items-center gap-1">
                <DollarSign className="w-4 h-4" />
                <span>¥{trip.total_budget}</span>
              </div>
            )}
          </div>

          {hasWeatherSummary(weatherSummary) && (
            <div className="mt-4 p-4 rounded-lg bg-primary/5 border border-primary/20">
              <div className="flex items-center gap-2">
                <Cloud className="w-5 h-5 text-primary" />
                <span className="font-medium text-foreground">天气概况</span>
              </div>
              <p className="mt-2 text-sm text-muted">
                {weatherSummary}
                {trip.weather_summary?.temperature_c && (
                  <span className="ml-2 font-medium text-foreground">
                    {trip.weather_summary.temperature_c}°C
                  </span>
                )}
              </p>
            </div>
          )}

          {trip.notes.length > 0 && (
            <div className="mt-4 space-y-2">
              {trip.notes.map((note, i) => (
                <p key={i} className="text-sm text-muted">
                  {note}
                </p>
              ))}
            </div>
          )}
        </header>

        {placesWithCoords.length > 0 && (
          <section className="mb-8">
            <h2 className="text-xl font-semibold text-foreground mb-4">
              行程地图
            </h2>
            <MapView places={placesWithCoords} />
          </section>
        )}

        <section>
          <h2 className="text-xl font-semibold text-foreground mb-4">
            行程安排
          </h2>
          <TimelineView
            items={trip.items}
            startDate={trip.input.date}
            tripDays={trip.input.days}
          />
        </section>
      </div>
    </main>
  );
}
