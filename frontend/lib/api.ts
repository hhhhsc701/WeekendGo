import type { TripInput, TripOutput, TripSummary } from "@/types/trip";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof payload.detail === "string" ? payload.detail : "Request failed");
  }
  return response.json() as Promise<T>;
}

export const api = {
  generateTrip(input: TripInput) {
    return request<TripOutput>("/api/trips/generate", {
      method: "POST",
      body: JSON.stringify(input),
    });
  },
  refineTrip(id: string, text: string) {
    return request<TripOutput | Record<string, unknown>>(`/api/trips/refine/${id}`, {
      method: "POST",
      body: JSON.stringify({ request: text }),
    });
  },
  getTrip(id: string) {
    return request<TripOutput>(`/api/trips/${id}`);
  },
  listTrips() {
    return request<TripSummary[]>("/api/trips");
  },
  getConfig() {
    return request<Record<string, unknown>>("/api/config");
  },
};
