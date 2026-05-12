"use client";

import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import {
  Calendar,
  MapPin,
  Clock,
  Users,
  DollarSign,
  Sparkles,
  Plane,
  MessageSquare,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { TripInput, CompanionType } from "@/types/trip";

interface TripFormProps {
  onSubmit: (input: TripInput) => Promise<void>;
}

const companionOptions: { value: CompanionType; label: string }[] = [
  { value: "solo", label: "独自旅行" },
  { value: "couple", label: "情侣出游" },
  { value: "family", label: "家庭旅行" },
  { value: "friends", label: "好友同行" },
];

const interestOptions = ["美食", "摄影", "历史", "自然风光", "博物馆", "亲子", "夜生活", "Citywalk"];

export function TripForm({ onSubmit }: TripFormProps) {
  const [city, setCity] = useState("");
  const [date, setDate] = useState("");
  const [days, setDays] = useState(2);
  const [budget, setBudget] = useState<string>("");
  const [interests, setInterests] = useState<string[]>([]);
  const [interestInput, setInterestInput] = useState("");
  const [companions, setCompanions] = useState<CompanionType>("solo");
  const [departureCity, setDepartureCity] = useState("");
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const dateInputRef = useRef<HTMLInputElement>(null);
  const interestInputRef = useRef<HTMLInputElement>(null);

  const openDatePicker = () => {
    dateInputRef.current?.showPicker?.();
  };

  const addInterest = (value: string) => {
    const normalized = value.trim();
    if (!normalized) return;
    setInterests((current) => {
      if (current.some((item) => item.toLowerCase() === normalized.toLowerCase())) {
        return current;
      }
      return [...current, normalized];
    });
    setErrors((current) => {
      if (!current.interests) return current;
      const rest = { ...current };
      delete rest.interests;
      return rest;
    });
    setInterestInput("");
  };

  const removeInterest = (value: string) => {
    setInterests((current) =>
      current.filter((item) => item.toLowerCase() !== value.toLowerCase())
    );
  };

  const handleInterestKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === "," || event.key === "，") {
      event.preventDefault();
      addInterest(interestInput);
    }
    if (event.key === "Backspace" && !interestInput && interests.length > 0) {
      removeInterest(interests[interests.length - 1]);
    }
  };

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};
    
    if (!city.trim()) {
      newErrors.city = "请输入目的地城市";
    }
    
    if (!date) {
      newErrors.date = "请选择出发日期";
    }
    
    if (days < 1 || days > 14) {
      newErrors.days = "行程天数需在1-14天之间";
    }
    
    if (interests.length === 0) {
      newErrors.interests = "请至少输入一个兴趣偏好";
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!validate()) return;
    
    setLoading(true);
    setErrors({});

    const input: TripInput = {
      city: city.trim(),
      date,
      days,
      budget: budget ? parseFloat(budget) : null,
      interests,
      companions,
      departure_city: departureCity.trim() || null,
      notes: notes.trim() || null,
    };
    
    try {
      await onSubmit(input);
    } catch (err) {
      setErrors({ submit: err instanceof Error ? err.message : "生成行程失败，请重试" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <MapPin className="w-4 h-4 text-primary" />
          目的地城市
        </label>
        <Input
          type="text"
          placeholder="例如：杭州、成都、大理..."
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className={errors.city ? "border-red-500 focus-visible:ring-red-500" : ""}
        />
        {errors.city && <p className="text-xs text-red-500">{errors.city}</p>}
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Plane className="w-4 h-4 text-primary" />
          出发城市（可选）
        </label>
        <Input
          type="text"
          placeholder="例如：北京、上海..."
          value={departureCity}
          onChange={(e) => setDepartureCity(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Calendar className="w-4 h-4 text-primary" />
          出发日期
        </label>
        <div className="relative">
          <Input
            ref={dateInputRef}
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            onClick={openDatePicker}
            min={new Date().toISOString().split("T")[0]}
            className={
              errors.date
                ? "cursor-pointer pr-10 border-red-500 focus-visible:ring-red-500 [&::-webkit-calendar-picker-indicator]:opacity-0"
                : "cursor-pointer pr-10 [&::-webkit-calendar-picker-indicator]:opacity-0"
            }
          />
          <Calendar
            className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground"
            aria-hidden="true"
          />
        </div>
        {errors.date && <p className="text-xs text-red-500">{errors.date}</p>}
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Clock className="w-4 h-4 text-primary" />
          行程天数
        </label>
        <Input
          type="number"
          min={1}
          max={14}
          value={days}
          onChange={(e) => setDays(parseInt(e.target.value) || 1)}
          className={errors.days ? "border-red-500 focus-visible:ring-red-500" : ""}
        />
        {errors.days && <p className="text-xs text-red-500">{errors.days}</p>}
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <DollarSign className="w-4 h-4 text-primary" />
          预算（元，可选）
        </label>
        <Input
          type="number"
          placeholder="例如：2000"
          value={budget}
          onChange={(e) => setBudget(e.target.value)}
          min={0}
        />
      </div>

      <div className="space-y-1.5">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Users className="w-4 h-4 text-primary" />
          同行人员
        </label>
        <select
          value={companions}
          onChange={(e) => setCompanions(e.target.value as CompanionType)}
          className="flex h-10 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
        >
          {companionOptions.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5 sm:col-span-2">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <Sparkles className="w-4 h-4 text-primary" />
          兴趣偏好
        </label>
        <div
          className={`flex min-h-10 w-full flex-wrap items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2 ${
            errors.interests ? "border-red-500" : "border-border"
          }`}
          onClick={() => interestInputRef.current?.focus()}
        >
          {interests.map((interest) => (
            <button
              key={interest}
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                removeInterest(interest);
              }}
              className="inline-flex h-6 items-center gap-1 rounded-full bg-primary/10 px-2 text-xs font-medium text-primary hover:bg-primary/15"
            >
              {interest}
              <X className="h-3 w-3" />
            </button>
          ))}
          <input
            id="interest-input"
            ref={interestInputRef}
            value={interestInput}
            onChange={(event) => setInterestInput(event.target.value)}
            onKeyDown={handleInterestKeyDown}
            onBlur={() => addInterest(interestInput)}
            placeholder={interests.length === 0 ? "输入后回车添加兴趣" : ""}
            className="h-6 min-w-[9rem] flex-1 bg-transparent outline-none placeholder:text-muted"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {interestOptions.map((option) => {
            const selected = interests.some(
              (interest) => interest.toLowerCase() === option.toLowerCase()
            );
            return (
              <button
                key={option}
                type="button"
                onClick={() => (selected ? removeInterest(option) : addInterest(option))}
                className={`h-7 rounded-full border px-3 text-xs font-medium transition-colors ${
                  selected
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted hover:border-primary/50 hover:text-foreground"
                }`}
              >
                {option}
              </button>
            );
          })}
        </div>
        {errors.interests && <p className="text-xs text-red-500">{errors.interests}</p>}
      </div>

      <div className="space-y-1.5 sm:col-span-2">
        <label className="flex items-center gap-1.5 text-sm font-medium text-foreground">
          <MessageSquare className="w-4 h-4 text-primary" />
          备注（可选）
        </label>
        <textarea
          placeholder="其他需求或偏好..."
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className="flex w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 resize-none"
        />
      </div>

      {errors.submit && (
        <div className="sm:col-span-2 p-3 rounded-md bg-red-50 border border-red-200 text-red-600 text-sm">
          {errors.submit}
        </div>
      )}

      <div className="sm:col-span-2">
        <Button
          type="submit"
          disabled={loading}
          className="w-full h-11 text-base font-semibold"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin w-5 h-5" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              正在生成行程...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Sparkles className="w-5 h-5" />
              生成周末行程
            </span>
          )}
        </Button>
      </div>
    </form>
  );
}
