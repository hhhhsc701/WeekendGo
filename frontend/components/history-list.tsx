"use client";

import Link from "next/link";
import type { TripSummary } from "@/types/trip";

export function HistoryList({ trips }: { trips: TripSummary[] }) {
  if (trips.length === 0) {
    return <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-500">No saved trips.</div>;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {trips.map((trip) => (
        <Link
          key={trip.id}
          className="rounded-md border border-slate-200 bg-white p-4 transition hover:border-emerald-700"
          href={`/itinerary/${trip.id}`}
        >
          <p className="text-sm font-semibold text-slate-950">{trip.summary}</p>
          <p className="mt-1 text-xs text-slate-500">Created {trip.created_at}</p>
        </Link>
      ))}
    </div>
  );
}
