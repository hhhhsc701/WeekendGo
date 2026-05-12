/**
 * TypeScript types matching backend Pydantic models in backend/app/models/trip.py
 */

export type CompanionType = "solo" | "couple" | "family" | "friends";

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface Place {
  name: string;
  address?: string | null;
  coordinates?: Coordinates | null;
  rating?: number | null;
  category?: string | null;
}

export interface WeatherSummary {
  summary: string;
  temperature_c?: number | null;
}

export interface TransportDetail {
  mode?: string | null;
  code?: string | null;
  departure?: string | null;
  arrival?: string | null;
  departure_coordinates?: Coordinates | null;
  arrival_coordinates?: Coordinates | null;
  departure_time?: string | null;
  arrival_time?: string | null;
  duration?: string | null;
  cost?: number | null;
}

export interface TripItem {
  start_time: string;
  end_time: string;
  activity: string;
  place: Place;
  estimated_cost?: number | null;
  transport?: string | null;
  transport_detail?: TransportDetail | null;
  notes?: string | null;
}

export interface TripInput {
  city: string;
  date: string; // ISO date string (YYYY-MM-DD)
  days: number;
  budget?: number | null;
  interests: string[];
  companions: CompanionType;
  departure_city?: string | null;
  departure_coordinates?: Coordinates | null;
  notes?: string | null;
}

export interface TripOutput {
  id: string;
  title: string;
  input: TripInput;
  region: string;
  items: TripItem[];
  weather_summary: WeatherSummary;
  total_budget?: number | null;
  notes: string[];
  created_at: string; // ISO datetime string
}
