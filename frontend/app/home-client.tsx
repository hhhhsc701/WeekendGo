"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Clock } from "lucide-react";
import { TripForm } from "@/components/trip-form";
import { ErrorState, LoadingState } from "@/components/status-message";
import { api } from "@/lib/api";
import type { TripInput } from "@/types/trip";

export function HomeClient() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(input: TripInput) {
    setLoading(true);
    setError(null);
    try {
      const trip = await api.generateTrip(input);
      router.push(`/itinerary/${trip.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Trip generation failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-6 py-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-emerald-700">WeekendGo</p>
          <h1 className="text-3xl font-semibold text-slate-950">Plan a weekend itinerary</h1>
        </div>
        <Link className="inline-flex items-center gap-2 text-sm font-medium text-slate-700" href="/history">
          <Clock className="h-4 w-4" />
          History
        </Link>
      </header>
      {error ? <ErrorState message={error} /> : null}
      {loading ? <LoadingState label="Generating itinerary" /> : null}
      <section className="rounded-md border border-slate-200 bg-white p-5">
        <TripForm loading={loading} onSubmit={submit} />
      </section>
    </main>
  );
}
