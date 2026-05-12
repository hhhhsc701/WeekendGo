"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { MapPin, Calendar, Clock, DollarSign, Trash2, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { deleteTrip } from "@/lib/api";
import type { TripOutput } from "@/types/trip";

interface ItineraryCardProps {
  trip: TripOutput;
  onDelete?: () => void;
}

function formatDateRange(dateStr: string, days: number): string {
  const startDate = new Date(dateStr);
  const endDate = new Date(startDate);
  endDate.setDate(startDate.getDate() + days - 1);

  const format = (d: Date) => `${d.getMonth() + 1}月${d.getDate()}日`;
  return `${format(startDate)} - ${format(endDate)}`;
}

function hasWeatherSummary(summary?: string | null): boolean {
  if (!summary) return false;
  const normalized = summary.trim();
  if (!normalized) return false;
  return !["不可用", "暂不可用", "无法获取", "unknown", "unavailable"].some((text) =>
    normalized.toLowerCase().includes(text)
  );
}

export function ItineraryCard({ trip, onDelete }: ItineraryCardProps) {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const weatherSummary = trip.weather_summary?.summary?.trim();

  const handleClick = () => {
    router.push(`/itinerary/${trip.id}`);
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (deleting) return;
    
    setDeleting(true);
    try {
      await deleteTrip(trip.id);
      onDelete?.();
    } catch (err) {
      console.error("删除行程失败:", err);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      onClick={handleClick}
      className="group bg-background rounded-lg border border-border shadow-sm hover:shadow-md hover:border-primary/30 transition-all cursor-pointer overflow-hidden"
    >
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-foreground truncate group-hover:text-primary transition-colors">
              {trip.title}
            </h3>

            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-2 text-sm text-muted">
                <MapPin className="w-4 h-4 shrink-0" />
                <span>{trip.input.city}</span>
                {trip.input.departure_city && (
                  <span className="text-xs opacity-70">
                    (从{trip.input.departure_city}出发)
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-sm text-muted">
                <Calendar className="w-4 h-4 shrink-0" />
                <span>{formatDateRange(trip.input.date, trip.input.days)}</span>
              </div>

              <div className="flex items-center gap-4 text-sm text-muted">
                <div className="flex items-center gap-1">
                  <Clock className="w-4 h-4 shrink-0" />
                  <span>{trip.input.days}天</span>
                </div>

                {trip.total_budget && (
                  <div className="flex items-center gap-1">
                    <DollarSign className="w-4 h-4 shrink-0" />
                    <span>¥{trip.total_budget}</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDelete}
              disabled={deleting}
              className="h-8 w-8 text-muted hover:text-red-500 hover:bg-red-50"
            >
              <Trash2 className="w-4 h-4" />
            </Button>

            <ChevronRight className="w-5 h-5 text-muted group-hover:text-primary transition-colors" />
          </div>
        </div>

        {hasWeatherSummary(weatherSummary) && (
          <div className="mt-4 pt-4 border-t border-border/50">
            <p className="text-sm text-muted">
              <span className="font-medium text-foreground">天气：</span>
              {weatherSummary}
              {trip.weather_summary?.temperature_c && (
                <span className="ml-2">
                  {trip.weather_summary.temperature_c}°C
                </span>
              )}
            </p>
          </div>
        )}
      </div>

      <div className="h-1 bg-gradient-to-r from-primary/0 via-primary to-primary/0 opacity-0 group-hover:opacity-100 transition-opacity" />
    </div>
  );
}
