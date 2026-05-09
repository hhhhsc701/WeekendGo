"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { HistoryList } from "@/components/history-list";
import { ErrorState, LoadingState } from "@/components/status-message";
import { api } from "@/lib/api";
import type { TripSummary } from "@/types/trip";

export default function HistoryPage() {
  const [trips, setTrips] = useState<TripSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void api
      .listTrips()
      .then(setTrips)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load history"));
  }, []);

  return (
    <main className="mx-auto min-h-screen w-full max-w-6xl px-6 py-8">
      <header className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-slate-950">Trip history</h1>
        <Link className="text-sm font-medium text-emerald-700" href="/">
          New trip
        </Link>
      </header>
      {error ? <ErrorState message={error} /> : null}
      {!trips && !error ? <LoadingState label="Loading history" /> : null}
      {trips ? <HistoryList trips={trips} /> : null}
    </main>
  );
}
