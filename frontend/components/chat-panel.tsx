"use client";

import { useState } from "react";
import { Send } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ErrorState, LoadingState } from "@/components/status-message";
import type { TripOutput } from "@/types/trip";

export function ChatPanel({ tripId, onUpdated }: { tripId: string; onUpdated: (trip: TripOutput) => void }) {
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; text: string }[]>([]);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!text.trim()) return;
    const request = text.trim();
    setMessages((current) => [...current, { role: "user", text: request }]);
    setText("");
    setLoading(true);
    setError(null);
    try {
      const result = await api.refineTrip(tripId, request);
      if ("items" in result) {
        onUpdated(result as TripOutput);
        setMessages((current) => [...current, { role: "assistant", text: "Itinerary updated." }]);
      } else {
        setMessages((current) => [
          ...current,
          { role: "assistant", text: String(result.clarification_question ?? "More detail is needed.") },
        ]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refinement failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="min-h-64 space-y-3 rounded-md border border-slate-200 bg-white p-4">
        {messages.length === 0 ? <p className="text-sm text-slate-500">Start with a change request.</p> : null}
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? "text-right" : "text-left"}>
            <span className="inline-block rounded-md bg-slate-100 px-3 py-2 text-sm text-slate-800">
              {message.text}
            </span>
          </div>
        ))}
      </div>
      {loading ? <LoadingState label="Refining itinerary" /> : null}
      {error ? <ErrorState message={error} /> : null}
      <div className="flex gap-2">
        <Textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="Move lunch later" />
        <Button aria-label="Send refinement" className="h-auto" disabled={loading} onClick={submit}>
          <Send className="h-4 w-4" />
        </Button>
      </div>
    </section>
  );
}
