import type { TripItem } from "@/types/trip";

export function TimelineView({ items }: { items: TripItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">No itinerary items yet.</p>;
  }
  return (
    <ol className="space-y-3">
      {items.map((item, index) => (
        <li key={`${item.start_time}-${item.place.name}-${index}`} className="grid grid-cols-[88px_1fr] gap-4">
          <div className="text-sm font-medium text-emerald-800">
            {item.start_time}
            <div className="text-xs font-normal text-slate-500">{item.end_time}</div>
          </div>
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-950">{item.activity}</h3>
                <p className="mt-1 text-sm text-slate-600">{item.place.name}</p>
                {item.place.address ? <p className="mt-1 text-xs text-slate-500">{item.place.address}</p> : null}
              </div>
              {item.estimated_cost != null ? (
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700">
                  {item.estimated_cost}
                </span>
              ) : null}
            </div>
            {item.transport ? <p className="mt-2 text-xs text-slate-500">Transport: {item.transport}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
