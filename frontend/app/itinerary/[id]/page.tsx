"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  MapPin,
  Calendar,
  Clock,
  DollarSign,
  Cloud,
  History,
  AlertCircle,
  Maximize2,
  Minimize2,
  Download,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { groupItemsByDay, TimelineView } from "@/components/timeline-view";
import { MapView } from "@/components/map-view";
import { getTrip, ApiError } from "@/lib/api";
import { getCityCoordinates } from "@/lib/city-coordinates";
import type { Coordinates, Place, TripItem, TripOutput } from "@/types/trip";

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

function parseLocalDate(dateStr: string): Date {
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

function formatDayDate(startDateStr: string, dayIndex: number): string {
  const date = addDays(parseLocalDate(startDateStr), dayIndex);
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  return `${date.getMonth() + 1}月${date.getDate()}日 ${weekdays[date.getDay()]}`;
}

function formatTime(timeStr: string): string {
  const timePart = timeStr.includes("T")
    ? timeStr.split("T")[1]
    : timeStr.includes(" ")
      ? timeStr.split(" ")[1]
      : timeStr;

  if (timePart.includes(":")) {
    const [hours, minutes] = timePart.split(":");
    return `${hours}:${minutes}`;
  }

  return timeStr;
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

function normalizeCityName(city?: string | null): string {
  return (city || "")
    .trim()
    .replace(/(市|省|自治区|特别行政区)$/u, "")
    .toLowerCase();
}

function isDepartureCityPlace(trip: TripOutput, place: Place): boolean {
  const departureCity = normalizeCityName(trip.input.departure_city);
  const destinationCity = normalizeCityName(trip.input.city);
  if (!departureCity || departureCity === destinationCity) return false;

  if (place.category === "departure") return true;

  const placeText = `${place.name || ""} ${place.address || ""}`.toLowerCase();
  if (placeText.includes(departureCity) && !placeText.includes(destinationCity)) {
    return true;
  }

  const departureCoordinates =
    trip.input.departure_coordinates || getCityCoordinates(trip.input.departure_city || "");
  if (!departureCoordinates || !hasValidCoordinates(place.coordinates)) return false;

  return distanceMeters(place.coordinates, departureCoordinates) <= 50000;
}

function buildMapPlaces(trip: TripOutput, items: TripItem[]): Place[] {
  const places: Place[] = [];
  const seen = new Set<string>();
  const destinationCoordinates = getCityCoordinates(trip.input.city);

  items.forEach((item) => {
    if (
      hasCoordinates(item) &&
      !isDepartureCityPlace(trip, item.place) &&
      isInDestinationCity(item.place, destinationCoordinates)
    ) {
      addUniquePlace(places, seen, item.place);
    }
  });

  return places;
}

function formatMoney(value?: number | null): string | null {
  if (value === null || value === undefined) return null;
  return `¥${value}`;
}

function companionLabel(value: TripOutput["input"]["companions"]): string {
  const labels: Record<TripOutput["input"]["companions"], string> = {
    solo: "独自出行",
    couple: "情侣",
    family: "家庭",
    friends: "朋友",
  };
  return labels[value] || value;
}

function formatTransportDetail(item: TripItem): string[] {
  const detail = item.transport_detail;
  if (!detail) return [];

  const lines: string[] = [];
  const modeLabel = detail.mode === "flight" ? "航班" : detail.mode === "train" ? "车次" : "交通";
  const summary = [modeLabel, detail.code].filter(Boolean).join(" ");
  if (summary) lines.push(`  具体交通：${summary}`);
  if (detail.departure || detail.arrival) {
    lines.push(`  路线：${[detail.departure, detail.arrival].filter(Boolean).join(" -> ")}`);
  }
  if (detail.departure_time || detail.arrival_time) {
    const transportTimes = [detail.departure_time, detail.arrival_time].filter(
      (value): value is string => Boolean(value)
    );
    lines.push(
      `  交通时间：${transportTimes.map(formatTime).join(" - ")}`
    );
  }
  if (detail.duration) lines.push(`  耗时：${detail.duration}`);
  if (detail.cost !== null && detail.cost !== undefined) lines.push(`  交通费用：¥${detail.cost}`);
  return lines;
}

function buildTripText(trip: TripOutput): string {
  const lines: string[] = [];
  const weatherSummary = trip.weather_summary?.summary?.trim();
  const dayGroups = groupItemsByDay(trip.items, trip.input.date, trip.input.days);

  lines.push(trip.title);
  lines.push("");
  lines.push(`目的地：${trip.input.city}`);
  if (trip.input.departure_city) lines.push(`出发城市：${trip.input.departure_city}`);
  lines.push(`出发日期：${formatDate(trip.input.date)}`);
  lines.push(`天数：${trip.input.days}天`);
  lines.push(`同行：${companionLabel(trip.input.companions)}`);
  lines.push(`兴趣：${trip.input.interests.join("、")}`);
  if (formatMoney(trip.input.budget)) lines.push(`预算：${formatMoney(trip.input.budget)}`);
  if (formatMoney(trip.total_budget)) lines.push(`预计总费用：${formatMoney(trip.total_budget)}`);
  if (hasWeatherSummary(weatherSummary)) {
    const temperature = trip.weather_summary?.temperature_c;
    lines.push(`天气：${weatherSummary}${temperature ? `，${temperature}°C` : ""}`);
  }
  if (trip.notes.length > 0) {
    lines.push("");
    lines.push("备注");
    trip.notes.forEach((note) => lines.push(`- ${note}`));
  }

  dayGroups.forEach((group) => {
    lines.push("");
    lines.push(`第${group.dayIndex + 1}天 ${formatDayDate(trip.input.date, group.dayIndex)}`);

    if (group.items.length === 0) {
      lines.push("当天暂无行程安排");
      return;
    }

    group.items.forEach((item, index) => {
      const cost = formatMoney(item.estimated_cost);
      lines.push(
        `${index + 1}. ${formatTime(item.start_time)}-${formatTime(item.end_time)} ${item.activity}${
          cost ? `（${cost}）` : ""
        }`
      );
      lines.push(`  地点：${item.place.name}${item.place.address ? `，${item.place.address}` : ""}`);
      if (item.transport) lines.push(`  交通：${item.transport}`);
      lines.push(...formatTransportDetail(item));
      if (item.notes) lines.push(`  备注：${item.notes}`);
    });
  });

  return `${lines.join("\n")}\n`;
}

function sanitizeFilename(value: string): string {
  return value
    .trim()
    .replace(/[\\/:*?"<>|]/g, "-")
    .replace(/\s+/g, "-")
    .slice(0, 80) || "行程";
}

function downloadText(filename: string, text: string): void {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
  const [mapExpanded, setMapExpanded] = useState(false);
  const [activeDayIndex, setActiveDayIndex] = useState(0);

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

  useEffect(() => {
    setActiveDayIndex(0);
  }, [id]);

  useEffect(() => {
    if (!trip) return;

    setActiveDayIndex((current) =>
      Math.min(Math.max(current, 0), Math.max(trip.input.days - 1, 0))
    );
  }, [trip]);

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
  const dayGroups = groupItemsByDay(trip.items, trip.input.date, trip.input.days);
  const activeDayGroup = dayGroups[activeDayIndex] || dayGroups[0];
  const activeDayItems = activeDayGroup?.items || [];
  const placesWithCoords = buildMapPlaces(trip, activeDayItems);
  const handleExportText = () => {
    const text = buildTripText(trip);
    downloadText(`${sanitizeFilename(trip.title)}.txt`, text);
  };

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

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleExportText}
            >
              <Download className="w-4 h-4 mr-2" />
              导出文本
            </Button>

            <Button
              variant="outline"
              onClick={() => router.push("/history")}
            >
              <History className="w-4 h-4 mr-2" />
              历史行程
            </Button>
          </div>
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

        {trip.items.length > 0 && (
          <section className="mb-8">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold text-foreground">
                  行程地图 · 第{(activeDayGroup?.dayIndex ?? activeDayIndex) + 1}天
                </h2>
                <p className="mt-1 text-sm text-muted">
                  显示当天 {activeDayItems.length} 个安排中的地点
                </p>
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setMapExpanded((expanded) => !expanded)}
              >
                {mapExpanded ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
                {mapExpanded ? "收起地图" : "展开地图"}
              </Button>
            </div>
            <MapView
              places={placesWithCoords}
              className={mapExpanded ? "h-[72vh] min-h-[520px]" : "h-[400px]"}
            />
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
            activeDayIndex={activeDayIndex}
            onActiveDayChange={setActiveDayIndex}
          />
        </section>
      </div>
    </main>
  );
}
