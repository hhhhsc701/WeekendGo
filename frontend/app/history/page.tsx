"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Sparkles, History, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ItineraryCard } from "@/components/itinerary-card";
import { listTrips } from "@/lib/api";
import type { TripOutput } from "@/types/trip";

export default function HistoryPage() {
  const router = useRouter();
  const [trips, setTrips] = useState<TripOutput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTrips = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await listTrips();
      setTrips(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载历史行程失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTrips();
  }, [fetchTrips]);

  const handleDelete = useCallback(() => {
    fetchTrips();
  }, [fetchTrips]);

  if (loading) {
    return (
      <main className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="flex items-center justify-between mb-6">
            <Button variant="ghost" onClick={() => router.push("/")}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回首页
            </Button>
          </div>

          <header className="mb-8">
            <div className="flex items-center gap-2 mb-2">
              <History className="w-6 h-6 text-primary" />
              <h1 className="text-2xl font-bold text-foreground">历史行程</h1>
            </div>
            <p className="text-muted">查看和管理你的所有行程记录</p>
          </header>

          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen bg-background">
        <div className="max-w-4xl mx-auto px-4 py-8">
          <div className="flex items-center justify-between mb-6">
            <Button variant="ghost" onClick={() => router.push("/")}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回首页
            </Button>
          </div>

          <header className="mb-8">
            <div className="flex items-center gap-2 mb-2">
              <History className="w-6 h-6 text-primary" />
              <h1 className="text-2xl font-bold text-foreground">历史行程</h1>
            </div>
            <p className="text-muted">查看和管理你的所有行程记录</p>
          </header>

          <div className="text-center py-12">
            <AlertCircle className="w-16 h-16 mx-auto mb-4 text-red-500" />
            <h2 className="text-xl font-semibold text-foreground mb-2">
              加载失败
            </h2>
            <p className="text-muted mb-6">{error}</p>
            <Button onClick={fetchTrips}>
              <RefreshCw className="w-4 h-4 mr-2" />
              重新加载
            </Button>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-background">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <Button variant="ghost" onClick={() => router.push("/")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            返回首页
          </Button>

          <Button variant="outline" onClick={fetchTrips}>
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
        </div>

        <header className="mb-8">
          <div className="flex items-center gap-2 mb-2">
            <History className="w-6 h-6 text-primary" />
            <h1 className="text-2xl font-bold text-foreground">历史行程</h1>
          </div>
          <p className="text-muted">查看和管理你的所有行程记录</p>
        </header>

        {trips.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-xl border border-border">
            <History className="w-16 h-16 mx-auto mb-4 text-muted opacity-50" />
            <h2 className="text-xl font-semibold text-foreground mb-2">
              暂无历史行程
            </h2>
            <p className="text-muted mb-6">
              开始规划你的第一个周末之旅吧！
            </p>
            <Button onClick={() => router.push("/")}>
              <Sparkles className="w-4 h-4 mr-2" />
              开始规划
            </Button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {trips.map((trip) => (
              <ItineraryCard
                key={trip.id}
                trip={trip}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}