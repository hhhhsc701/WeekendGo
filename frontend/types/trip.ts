export type CompanionType = "solo" | "couple" | "family" | "friends";
export type Region = "domestic" | "international";

export interface TripInput {
  city: string;
  date: string;
  days: number;
  budget?: number | null;
  interests: string[];
  companions: CompanionType;
  departure_city?: string | null;
  notes?: string | null;
}

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface Place {
  name: string;
  address?: string | null;
  coordinates?: Coordinates | null;
  rating?: number | null;
  distance_meters?: number | null;
  category?: string | null;
}

export interface TripItem {
  start_time: string;
  end_time: string;
  activity: string;
  place: Place;
  estimated_cost?: number | null;
  transport?: string | null;
  notes?: string | null;
}

export interface TripOutput {
  id: string;
  title: string;
  input: TripInput;
  region: Region;
  items: TripItem[];
  total_budget?: number | null;
  weather_summary: {
    summary: string;
    temperature_c?: number | null;
    rain_probability?: number | null;
  };
  transportation: {
    summary: string;
    trains: Record<string, unknown>[];
  };
  notes: string[];
  created_at: string;
}

export interface TripSummary {
  id: string;
  city: string;
  date: string;
  created_at: string;
  updated_at: string;
  summary: string;
}
