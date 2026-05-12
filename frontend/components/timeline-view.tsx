"use client";

import { Clock, MapPin, DollarSign, Car, Info, Plane, Train } from "lucide-react";
import type { TransportDetail, TripItem } from "@/types/trip";

interface TimelineViewProps {
  items: TripItem[];
  startDate: string;
  tripDays: number;
}

interface DayGroup {
  dayIndex: number;
  items: TripItem[];
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

function getItemDate(value: string): Date | null {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function getMinutes(value: string): number | null {
  const timePart = value.includes("T")
    ? value.split("T")[1]
    : value.includes(" ")
      ? value.split(" ")[1]
      : value;
  const match = timePart.match(/^(\d{1,2}):(\d{2})/);
  if (!match) return null;
  return Number(match[1]) * 60 + Number(match[2]);
}

function diffDays(date: Date, startDate: Date): number {
  const oneDay = 24 * 60 * 60 * 1000;
  return Math.round((date.getTime() - startDate.getTime()) / oneDay);
}

function groupItemsByDay(items: TripItem[], startDateStr: string, tripDays: number): DayGroup[] {
  const startDate = parseLocalDate(startDateStr);
  const inferred = new Map<number, TripItem[]>();
  let currentDay = 0;
  let previousMinutes: number | null = null;

  items.forEach((item) => {
    const explicitDate = getItemDate(item.start_time);
    const explicitDay = explicitDate ? diffDays(explicitDate, startDate) : null;
    const minutes = getMinutes(item.start_time);

    if (explicitDay !== null && explicitDay >= 0 && explicitDay < tripDays) {
      currentDay = explicitDay;
    } else if (
      minutes !== null &&
      previousMinutes !== null &&
      minutes < previousMinutes - 30 &&
      currentDay < tripDays - 1
    ) {
      currentDay += 1;
    }

    const existing = inferred.get(currentDay) || [];
    existing.push(item);
    inferred.set(currentDay, existing);
    previousMinutes = minutes;
  });

  if (inferred.size === 1 && tripDays > 1 && items.length >= tripDays * 2) {
    const chunkSize = Math.ceil(items.length / tripDays);
    return Array.from({ length: tripDays }, (_, dayIndex) => ({
      dayIndex,
      items: items.slice(dayIndex * chunkSize, (dayIndex + 1) * chunkSize),
    })).filter((group) => group.items.length > 0);
  }

  return Array.from(inferred.entries())
    .sort(([a], [b]) => a - b)
    .map(([dayIndex, groupItems]) => ({ dayIndex, items: groupItems }));
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

function formatDayLabel(startDateStr: string, dayIndex: number): string {
  const date = addDays(parseLocalDate(startDateStr), dayIndex);
  const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const weekday = weekdays[date.getDay()];
  const month = date.getMonth() + 1;
  const day = date.getDate();
  
  return `第${dayIndex + 1}天 · ${month}月${day}日 ${weekday}`;
}

function hasTransportDetail(detail?: TransportDetail | null): detail is TransportDetail {
  return Boolean(
    detail &&
      (detail.code ||
        detail.departure_time ||
        detail.arrival_time ||
        detail.cost !== null && detail.cost !== undefined)
  );
}

function transportModeLabel(detail: TransportDetail): string {
  if (detail.mode === "flight") return "航班";
  if (detail.mode === "train") return "车次";
  return "交通";
}

function formatTransportRoute(detail: TransportDetail): string | null {
  if (detail.departure && detail.arrival) {
    return `${detail.departure} → ${detail.arrival}`;
  }
  return detail.departure || detail.arrival || null;
}

function formatTransportTime(detail: TransportDetail): string | null {
  if (detail.departure_time && detail.arrival_time) {
    return `${formatTime(detail.departure_time)} - ${formatTime(detail.arrival_time)}`;
  }
  return detail.departure_time || detail.arrival_time || null;
}

export function TimelineView({ items, startDate, tripDays }: TimelineViewProps) {
  if (items.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
        <p>暂无行程安排</p>
      </div>
    );
  }

  const groupedItems = groupItemsByDay(items, startDate, tripDays);

  return (
    <div className="space-y-8">
      {groupedItems.map((group) => (
        <div key={group.dayIndex} className="relative">
          <div className="mb-4 pb-2 border-b border-border">
            <h3 className="text-lg font-semibold text-foreground">
              {formatDayLabel(startDate, group.dayIndex)}
            </h3>
          </div>

          <div className="relative pl-8">
            <div className="absolute left-3 top-0 bottom-0 w-0.5 bg-border" />

            {group.items.map((item, itemIndex) => (
              <div key={`${group.dayIndex}-${itemIndex}`} className="relative mb-6 last:mb-0">
                <div className="absolute left-[-5px] top-2 w-2.5 h-2.5 rounded-full bg-primary ring-4 ring-background" />

                <div className="bg-background rounded-lg border border-border p-4 shadow-sm hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 text-sm text-muted mb-2">
                        <Clock className="w-4 h-4" />
                        <span>
                          {formatTime(item.start_time)} - {formatTime(item.end_time)}
                        </span>
                      </div>

                      <h4 className="text-base font-medium text-foreground mb-1">
                        {item.activity}
                      </h4>

                      <div className="flex items-center gap-2 text-sm text-muted">
                        <MapPin className="w-4 h-4" />
                        <span>{item.place.name}</span>
                        {item.place.address && (
                          <span className="text-xs opacity-70">
                            · {item.place.address}
                          </span>
                        )}
                      </div>
                    </div>

                    {item.estimated_cost !== null && item.estimated_cost !== undefined && (
                      <div className="flex items-center gap-1 text-sm font-medium text-primary shrink-0">
                        <DollarSign className="w-4 h-4" />
                        <span>¥{item.estimated_cost}</span>
                      </div>
                    )}
                  </div>

                  {item.transport && (
                    <div className="mt-3 pt-3 border-t border-border/50 flex items-center gap-2 text-sm text-muted">
                      <Car className="w-4 h-4" />
                      <span>{item.transport}</span>
                    </div>
                  )}

                  {hasTransportDetail(item.transport_detail) && (
                    <div className="mt-3 rounded-md border border-primary/20 bg-primary/5 p-3 text-sm">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        {item.transport_detail.mode === "flight" ? (
                          <Plane className="h-4 w-4 text-primary" />
                        ) : (
                          <Train className="h-4 w-4 text-primary" />
                        )}
                        <span className="font-medium text-foreground">
                          {transportModeLabel(item.transport_detail)}
                          {item.transport_detail.code ? ` ${item.transport_detail.code}` : ""}
                        </span>
                        {formatTransportRoute(item.transport_detail) && (
                          <span className="text-muted">
                            {formatTransportRoute(item.transport_detail)}
                          </span>
                        )}
                      </div>
                      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-muted">
                        {formatTransportTime(item.transport_detail) && (
                          <span>时间：{formatTransportTime(item.transport_detail)}</span>
                        )}
                        {item.transport_detail.duration && (
                          <span>耗时：{item.transport_detail.duration}</span>
                        )}
                        {item.transport_detail.cost !== null && item.transport_detail.cost !== undefined && (
                          <span className="font-medium text-primary">
                            费用：¥{item.transport_detail.cost}
                          </span>
                        )}
                      </div>
                    </div>
                  )}

                  {item.notes && (
                    <div className="mt-2 flex items-start gap-2 text-sm text-muted">
                      <Info className="w-4 h-4 shrink-0 mt-0.5" />
                      <span>{item.notes}</span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
