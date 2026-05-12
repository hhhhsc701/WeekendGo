"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, History, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { TripForm } from "@/components/trip-form";
import { generateTrip } from "@/lib/api";
import type { TripInput } from "@/types/trip";

export default function HomePage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (input: TripInput) => {
    setError(null);
    
    try {
      const trip = await generateTrip(input);
      router.push(`/itinerary/${trip.id}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "生成行程失败，请稍后重试";
      setError(message);
    }
  };

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12">
        <header className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <Sparkles className="w-8 h-8 text-primary" />
            <h1 className="text-3xl sm:text-4xl font-bold text-foreground">
              WeekendGo
            </h1>
          </div>
          <p className="text-lg text-muted">
            AI 智能周末行程规划助手
          </p>
        </header>

        <div className="bg-white rounded-xl border border-border shadow-sm p-6 sm:p-8">
          <h2 className="text-xl font-semibold text-foreground mb-6">
            开始规划你的周末之旅
          </h2>

          {error && (
            <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-700">生成失败</p>
                <p className="text-sm text-red-600 mt-1">{error}</p>
              </div>
            </div>
          )}

          <TripForm onSubmit={handleSubmit} />
        </div>

        <div className="mt-8 text-center">
          <Button
            variant="outline"
            onClick={() => router.push("/history")}
            className="inline-flex items-center gap-2"
          >
            <History className="w-4 h-4" />
            查看历史行程
          </Button>
        </div>
      </div>
    </main>
  );
}