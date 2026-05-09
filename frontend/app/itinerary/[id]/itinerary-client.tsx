"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ItineraryCard } from "@/components/itinerary-card";
import { ErrorState, LoadingState } from "@/components/status-message";
import { api } from "@/lib/api";
import type { TripOutput } from "@/types/trip";

export function ItineraryClient({ tripId }: { tripId: string }) {
  const [trip, setTrip] = useState<TripOutput | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .getTrip(tripId)
      .then(setTrip)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load trip"));
  }, [tripId]);

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-6 py-8">
      <Link className="text-sm font-medium text-emerald-700" href="/">
        New trip
      </Link>
      <div className="mt-6">
        {error ? <ErrorState message={error} /> : null}
        {!trip && !error ? <LoadingState label="Loading itinerary" /> : null}
        {trip ? <ItineraryCard trip={trip} /> : null}
      </div>
    </main>
  );
}
