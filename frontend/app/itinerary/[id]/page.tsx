import { ItineraryClient } from "@/app/itinerary/[id]/itinerary-client";

export default async function ItineraryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ItineraryClient tripId={id} />;
}
