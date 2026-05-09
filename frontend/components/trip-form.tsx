"use client";

import { useMemo, useState } from "react";
import { CalendarDays, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { CompanionType, TripInput } from "@/types/trip";

const interestOptions = ["outdoor", "food", "photography", "culture", "coffee", "shopping"];
const companionOptions: { label: string; value: CompanionType }[] = [
  { label: "Solo", value: "solo" },
  { label: "Couple", value: "couple" },
  { label: "Family", value: "family" },
  { label: "Friends", value: "friends" },
];

export function TripForm({
  onSubmit,
  loading,
}: {
  onSubmit: (input: TripInput) => Promise<void> | void;
  loading?: boolean;
}) {
  const [city, setCity] = useState("Shanghai");
  const [date, setDate] = useState("");
  const [days, setDays] = useState(1);
  const [budget, setBudget] = useState("");
  const [interests, setInterests] = useState<string[]>(["food", "culture"]);
  const [companions, setCompanions] = useState<CompanionType>("friends");
  const [departureCity, setDepartureCity] = useState("");
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const errors = useMemo(() => {
    const result: Record<string, string> = {};
    if (!city.trim()) result.city = "City is required";
    if (!date) result.date = "Date is required";
    if (interests.length === 0) result.interests = "Choose at least one interest";
    return result;
  }, [city, date, interests]);

  function toggleInterest(value: string) {
    setInterests((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(errors).length > 0) return;
    await onSubmit({
      city: city.trim(),
      date,
      days,
      budget: budget ? Number(budget) : null,
      interests,
      companions,
      departure_city: departureCity.trim() || null,
      notes: notes.trim() || null,
    });
  }

  return (
    <form className="grid gap-5 lg:grid-cols-[1fr_1fr]" onSubmit={handleSubmit}>
      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-800">City</span>
        <Input value={city} onChange={(event) => setCity(event.target.value)} placeholder="Shanghai" />
        {submitted && errors.city ? <FieldError text={errors.city} /> : null}
      </label>

      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-800">Date</span>
        <div className="relative">
          <CalendarDays className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <Input className="pl-9" type="date" value={date} onChange={(event) => setDate(event.target.value)} />
        </div>
        {submitted && errors.date ? <FieldError text={errors.date} /> : null}
      </label>

      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-800">Days</span>
        <Input
          min={1}
          max={14}
          type="number"
          value={days}
          onChange={(event) => setDays(Number(event.target.value))}
        />
      </label>

      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-800">Budget</span>
        <Input value={budget} onChange={(event) => setBudget(event.target.value)} placeholder="800" type="number" />
      </label>

      <fieldset className="space-y-2 lg:col-span-2">
        <legend className="text-sm font-medium text-slate-800">Interests</legend>
        <div className="flex flex-wrap gap-2">
          {interestOptions.map((interest) => (
            <button
              key={interest}
              type="button"
              onClick={() => toggleInterest(interest)}
              className={`rounded-md border px-3 py-2 text-sm transition ${
                interests.includes(interest)
                  ? "border-emerald-700 bg-emerald-50 text-emerald-800"
                  : "border-slate-300 bg-white text-slate-700"
              }`}
            >
              {interest}
            </button>
          ))}
        </div>
        {submitted && errors.interests ? <FieldError text={errors.interests} /> : null}
      </fieldset>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium text-slate-800">Companions</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
          {companionOptions.map((option) => (
            <label
              key={option.value}
              className="flex h-10 items-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-700"
            >
              <input
                checked={companions === option.value}
                name="companions"
                onChange={() => setCompanions(option.value)}
                type="radio"
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>

      <label className="space-y-2">
        <span className="text-sm font-medium text-slate-800">Departure city</span>
        <Input value={departureCity} onChange={(event) => setDepartureCity(event.target.value)} placeholder="Beijing" />
      </label>

      <label className="space-y-2 lg:col-span-2">
        <span className="text-sm font-medium text-slate-800">Notes</span>
        <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Prefer relaxed pacing" />
      </label>

      <div className="lg:col-span-2">
        <Button className="gap-2" disabled={loading} type="submit">
          <Send className="h-4 w-4" />
          Generate itinerary
        </Button>
      </div>
    </form>
  );
}

function FieldError({ text }: { text: string }) {
  return <p className="text-xs text-red-600">{text}</p>;
}
