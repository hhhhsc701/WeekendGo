/**
 * API client for backend REST endpoints
 * Matches backend/app/api/routes.py
 */

import type { TripInput, TripOutput } from "@/types/trip";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const API_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS || 180000);

class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function fetchApi<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const error = await response.json();
        message = error.detail || error.message || message;
      } catch {
        // Use default message if JSON parsing fails
      }
      throw new ApiError(response.status, message);
    }

    return response.json();
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(408, "请求超时，生成行程耗时过长，请稍后重试");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

/**
 * Generate a new trip itinerary
 * POST /api/trips/generate
 */
export async function generateTrip(input: TripInput): Promise<TripOutput> {
  return fetchApi<TripOutput>("/api/trips/generate", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * Get a trip by ID
 * GET /api/trips/:id
 */
export async function getTrip(id: string): Promise<TripOutput> {
  return fetchApi<TripOutput>(`/api/trips/${id}`);
}

/**
 * List all trips
 * GET /api/trips
 */
export async function listTrips(): Promise<TripOutput[]> {
  return fetchApi<TripOutput[]>("/api/trips");
}

/**
 * Delete a trip by ID
 * DELETE /api/trips/:id
 */
export async function deleteTrip(id: string): Promise<{ deleted: boolean }> {
  return fetchApi<{ deleted: boolean }>(`/api/trips/${id}`, {
    method: "DELETE",
  });
}

export { ApiError };
