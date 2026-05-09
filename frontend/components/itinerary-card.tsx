import { MessageSquare, Share2 } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { MapView } from "@/components/map-view";
import { TimelineView } from "@/components/timeline-view";
import type { TripOutput } from "@/types/trip";

export function ItineraryCard({ trip }: { trip: TripOutput }) {
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-emerald-700">{trip.input.city}</p>
          <h2 className="text-2xl font-semibold text-slate-950">{trip.title}</h2>
          <p className="mt-1 text-sm text-slate-600">{trip.weather_summary.summary}</p>
        </div>
        <div className="flex gap-2">
          <Link href={`/chat/${trip.id}`}>
            <Button className="gap-2" variant="secondary">
              <MessageSquare className="h-4 w-4" />
              Refine
            </Button>
          </Link>
          <Button aria-label="Share itinerary" variant="ghost">
            <Share2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
        <TimelineView items={trip.items} />
        <div className="space-y-4">
          <MapView trip={trip} />
          <div className="rounded-md border border-slate-200 bg-white p-4 text-sm text-slate-600">
            <p>Total budget: {trip.total_budget ?? "Not estimated"}</p>
            <p className="mt-1">Transport: {trip.transportation.summary}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
