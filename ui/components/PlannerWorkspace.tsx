"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { SectionKey } from "@/app/page";
import type { FlightCard, HotelCard, TripProfileSnapshot } from "@/lib/types";
import { syncProfile } from "@/lib/api";

interface PlannerWorkspaceProps {
  activeSection: SectionKey;
  onSectionChange?: (s: SectionKey) => void;
  flightResults: Array<{ label: string; cards: FlightCard[] }>;
  hotelResults: Array<{ label: string; cards: HotelCard[] }>;
  profile: TripProfileSnapshot | null;
  sessionId?: string;
  onOpenChat?: () => void;
}

// ── Snapshot autocomplete ──────────────────────────────────────────────────

const DESTINATION_SUGGESTIONS = [
  "Tokyo, Japan",
  "Kyoto, Japan",
  "Osaka, Japan",
  "Seoul, South Korea",
  "Bangkok, Thailand",
  "Singapore",
  "Bali, Indonesia",
  "Paris, France",
  "Rome, Italy",
  "London, United Kingdom",
  "Barcelona, Spain",
  "Lisbon, Portugal",
  "New York, USA",
  "Los Angeles, USA",
  "Atlanta, Georgia",
];

const FROM_CITY_SUGGESTIONS = [
  "Los Angeles, California",
  "New York, New York",
  "Atlanta, Georgia",
  "Chicago, Illinois",
  "Seattle, Washington",
  "San Francisco, California",
  "Miami, Florida",
  "Dallas, Texas",
  "London, United Kingdom",
  "Tokyo, Japan",
];

const POPULAR_CITY_BOOST: Record<string, number> = {
  atlanta: 40,
  tokyo: 40,
  london: 35,
  paris: 35,
  rome: 30,
  bangkok: 30,
  singapore: 30,
  barcelona: 25,
  lisbon: 20,
  "new york": 40,
  "los angeles": 30,
};

type NominatimRow = {
  importance?: number;
  addresstype?: string;
  display_name?: string;
  address?: {
    city?: string;
    town?: string;
    village?: string;
    municipality?: string;
    hamlet?: string;
    state?: string;
    country?: string;
  };
};

function rankPlaceSuggestions(
  rows: NominatimRow[],
  query: string,
  localFallback: string[],
): string[] {
  const qLower = query.trim().toLowerCase();
  const normalized = rows
    .map((r) => {
      const a = r.address || {};
      const rawLocality =
        a.city || a.town || a.village || a.municipality || a.hamlet || "";
      const locality = rawLocality.trim();
      const region = a.state || a.country || "";
      const label = locality
        ? region
          ? `${locality}, ${region}`
          : locality
        : (r.display_name || "").split(",").slice(0, 2).join(",").trim();
      return {
        label,
        locality: locality || label.split(",")[0] || "",
        hasLocality: Boolean(locality),
        importance: Number(r.importance || 0),
        addresstype: (r.addresstype || "").toLowerCase(),
      };
    })
    .filter((x) => x.label);

  const withoutCounties = normalized.filter((x) => {
    const t = x.addresstype;
    const l = x.label.toLowerCase();
    const loc = x.locality.toLowerCase();
    if (t === "county") return false;
    if (l.includes("county")) return false;
    if (loc.includes("county")) return false;
    return true;
  });

  const strongMatches = withoutCounties.filter((x) => {
    const loc = x.locality.trim().toLowerCase();
    return loc.startsWith(qLower) || loc.includes(qLower);
  });
  const pool = strongMatches.length > 0 ? strongMatches : withoutCounties;

  const ranked = pool.sort((a, b) => {
    const aLoc = a.locality.trim().toLowerCase();
    const bLoc = b.locality.trim().toLowerCase();
    const aStarts = aLoc.startsWith(qLower) ? 1 : 0;
    const bStarts = bLoc.startsWith(qLower) ? 1 : 0;
    if (aStarts !== bStarts) return bStarts - aStarts;
    const aHasLocality = a.hasLocality ? 1 : 0;
    const bHasLocality = b.hasLocality ? 1 : 0;
    if (aHasLocality !== bHasLocality) return bHasLocality - aHasLocality;
    const aBoost = POPULAR_CITY_BOOST[aLoc] || 0;
    const bBoost = POPULAR_CITY_BOOST[bLoc] || 0;
    if (aBoost !== bBoost) return bBoost - aBoost;
    const cityLike = new Set(["city", "town", "village", "municipality", "hamlet"]);
    const aCity = cityLike.has(a.addresstype) ? 1 : 0;
    const bCity = cityLike.has(b.addresstype) ? 1 : 0;
    if (aCity !== bCity) return bCity - aCity;
    return b.importance - a.importance;
  });

  const liveSuggestions = ranked.map((x) => x.label);
  const merged = [...liveSuggestions, ...localFallback];
  return Array.from(new Set(merged)).slice(0, 6);
}

// ── Date helpers ──────────────────────────────────────────────────────────

function toDate(value: string): Date | null {
  if (!value) return null;
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function toYmd(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function addMonths(base: Date, delta: number): Date {
  return new Date(base.getFullYear(), base.getMonth() + delta, 1);
}

function sameDay(a: Date, b: Date) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function inDateRange(day: Date, start: Date, end: Date) {
  const t = day.getTime();
  return t >= start.getTime() && t <= end.getTime();
}

function buildMonthGrid(monthBase: Date): Array<Date | null> {
  const y = monthBase.getFullYear();
  const m = monthBase.getMonth();
  const first = new Date(y, m, 1);
  const leading = first.getDay();
  const days = new Date(y, m + 1, 0).getDate();
  const cells: Array<Date | null> = [];
  for (let i = 0; i < leading; i++) cells.push(null);
  for (let d = 1; d <= days; d++) cells.push(new Date(y, m, d));
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

// ── Stat field (snapshot) ─────────────────────────────────────────────────

function SnapshotField({
  label,
  children,
  wide,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div
      className={`flex flex-col gap-1 rounded-xl border border-black/[0.04] bg-stone-50/60 px-3 py-2.5 ${wide ? "col-span-2" : ""}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
        {label}
      </p>
      {children}
    </div>
  );
}

// ── Autocomplete input ─────────────────────────────────────────────────────

function AutoInput({
  value,
  onChange,
  placeholder,
  suggestions,
  onFocus,
  onBlur,
  focused,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  suggestions: string[];
  onFocus: () => void;
  onBlur: () => void;
  focused: boolean;
}) {
  return (
    <div className="relative">
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={onFocus}
        onBlur={onBlur}
        placeholder={placeholder}
        className="w-full text-sm font-medium text-stone-800 bg-transparent outline-none placeholder:text-stone-400"
      />
      {focused && suggestions.length > 0 && (
        <div className="absolute left-0 top-full mt-1 z-30 w-64 rounded-xl border border-black/[0.07] bg-white shadow-float overflow-hidden">
          {suggestions.map((opt) => (
            <button
              key={opt}
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(opt);
                onBlur();
              }}
              className="block w-full px-3 py-2 text-left text-sm text-stone-700 hover:bg-indigo-50 transition-colors"
            >
              {opt}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Flight option row ─────────────────────────────────────────────────────

function FlightRow({
  card,
  onSave,
  saved,
}: {
  card: FlightCard;
  onSave?: (card: FlightCard) => void;
  saved?: boolean;
}) {
  const stopText =
    card.stops === 0 ? "Nonstop" : `${card.stops} stop${card.stops > 1 ? "s" : ""}`;
  return (
    <div
      className={`rounded-xl border p-3 ${
        saved
          ? "bg-emerald-50 border-emerald-200"
          : "bg-stone-50/60 hover:bg-white hover:shadow-card"
      } transition-all group`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          {/* Airline mark */}
          {card.airline_logo ? (
            <img
              src={card.airline_logo}
              alt={`${card.airline} logo`}
              className="w-10 h-10 rounded-lg border border-black/[0.06] bg-white object-contain p-1.5 shrink-0"
            />
          ) : (
            <div className="w-10 h-10 rounded-lg border border-black/[0.06] bg-indigo-50 flex items-center justify-center shrink-0">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                strokeLinecap="round"
                strokeLinejoin="round"
                className="w-4 h-4 text-indigo-600"
                aria-hidden
              >
                <path d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
              </svg>
            </div>
          )}

          <div className="min-w-0">
            <p className="text-base font-semibold text-stone-800 truncate">{card.airline}</p>
            <div className="mt-1 flex flex-wrap items-center gap-1.5">
              <span className="inline-flex items-center rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">
                {stopText}
              </span>
              <span className="inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
                {card.duration}
              </span>
            </div>
          </div>
        </div>

        {/* Price */}
        <div className="text-right shrink-0">
          <p className="text-2xl font-bold leading-none text-indigo-600">${card.price}</p>
          <p className="text-[10px] text-stone-400 mt-1">per person</p>
        </div>
      </div>

      {/* Route timeline */}
      <div className="mt-3 rounded-xl border border-black/[0.04] bg-white/90 px-3 py-2.5">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-stone-800">{card.departure.code}</p>
            <p className="text-[11px] text-stone-500">{card.departure.time}</p>
          </div>
          <div className="flex items-center gap-1.5 text-stone-400">
            <span className="h-px w-10 bg-stone-300" />
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-3.5 h-3.5"
              aria-hidden
            >
              <path d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
            <span className="h-px w-10 bg-stone-300" />
          </div>
          <div className="min-w-0 text-right">
            <p className="text-sm font-semibold text-stone-800">{card.arrival.code}</p>
            <p className="text-[11px] text-stone-500">{card.arrival.time}</p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-3 flex items-center gap-2">
        {card.url && (
          <a
            href={card.url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-xl border border-black/[0.07] bg-white px-2.5 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-100 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
              <path d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
            View details
          </a>
        )}
        {onSave && (
          <button
            onClick={() => onSave(card)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
              <path d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
            </svg>
            Save option
          </button>
        )}
        <div className="ml-auto" />

        {/* Saved chip */}
        {saved && (
          <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-700 border-emerald-200 shrink-0">
            Saved
          </span>
        )}
      </div>
    </div>
  );
}

// ── Hotel option row ──────────────────────────────────────────────────────

function HotelRow({
  card,
  onSave,
  saved,
}: {
  card: HotelCard;
  onSave?: (card: HotelCard) => void;
  saved?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-xl border border-black/[0.04] ${
        saved
          ? "bg-emerald-50 border-emerald-200"
          : "bg-stone-50/60 hover:bg-white hover:shadow-card"
      } transition-all group`}
    >
      {/* Icon tile */}
      <div className="w-9 h-9 rounded-xl bg-violet-100 flex items-center justify-center shrink-0">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="w-4 h-4 text-violet-600"
          aria-hidden
        >
          <path d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
        </svg>
      </div>

      {/* Main info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-stone-800 truncate">
          {card.name}
        </p>
        <p className="text-[11px] text-stone-400 mt-0.5">
          {card.hotel_class ? `${card.hotel_class} · ` : ""}
          {card.rating !== undefined
            ? `${card.rating}/5`
            : "Rating unavailable"}
          {card.reviews ? ` (${card.reviews} reviews)` : ""}
        </p>
      </div>

      {/* Price */}
      <div className="text-right shrink-0">
        <p className="text-sm font-bold text-indigo-600">
          {card.price_per_night || "N/A"}
        </p>
        <p className="text-[10px] text-stone-400">per night</p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-all ml-1">
        {card.link && (
          <a
            href={card.link}
            target="_blank"
            rel="noreferrer"
            className="w-7 h-7 rounded-lg border border-black/[0.07] bg-white flex items-center justify-center text-stone-400 hover:bg-stone-100 transition-colors"
            title="View details"
            aria-label="View hotel details"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
              <path d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
            </svg>
          </a>
        )}
        {onSave && (
          <button
            onClick={() => onSave(card)}
            className="w-7 h-7 rounded-lg border border-indigo-200 bg-white flex items-center justify-center text-indigo-500 hover:bg-indigo-50 transition-all"
            title="Save this hotel"
            aria-label="Save hotel"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
              <path d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z" />
            </svg>
          </button>
        )}
      </div>

      {/* Saved chip */}
      {saved && (
        <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-700 border-emerald-200 shrink-0">
          Saved
        </span>
      )}
    </div>
  );
}

// ── Section card ──────────────────────────────────────────────────────────

const SECTION_META: Record<SectionKey, { label: string; description: string; color: string }> = {
  flights: {
    label: "Flights",
    description: "Search and save flight options for your trip.",
    color: "text-indigo-600 bg-indigo-50",
  },
  hotels: {
    label: "Hotels",
    description: "Explore and save accommodation options.",
    color: "text-violet-600 bg-violet-50",
  },
  itinerary: {
    label: "Itinerary",
    description: "Your day-by-day plan will appear here.",
    color: "text-sky-600 bg-sky-50",
  },
  transportation: {
    label: "Transportation",
    description: "Local transport tips and options.",
    color: "text-emerald-600 bg-emerald-50",
  },
  budget: {
    label: "Budget",
    description: "Cost estimates and budget breakdown.",
    color: "text-amber-600 bg-amber-50",
  },
  packing: {
    label: "Packing",
    description: "Tailored packing list for your trip.",
    color: "text-pink-600 bg-pink-50",
  },
  advisory: {
    label: "Travel Advisory",
    description: "Visa requirements and safety information.",
    color: "text-stone-600 bg-stone-100",
  },
};

// ── Main component ────────────────────────────────────────────────────────

export default function PlannerWorkspace({
  activeSection,
  flightResults,
  hotelResults,
  profile,
  sessionId,
  onOpenChat,
}: PlannerWorkspaceProps) {
  const [savedFlight, setSavedFlight] = useState<FlightCard | null>(null);
  const [savedHotel, setSavedHotel] = useState<HotelCard | null>(null);

  const [snapshotInput, setSnapshotInput] = useState({
    destination: "",
    from: "",
    travelers: "",
    style: "",
    budget: "",
    startDate: "",
    endDate: "",
  });

  const [datePickerOpen, setDatePickerOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(
    () => new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const dateButtonRef = useRef<HTMLButtonElement>(null);
  const [calendarAnchor, setCalendarAnchor] = useState<{ top: number; left: number } | null>(null);

  const [destinationFocused, setDestinationFocused] = useState(false);
  const [destinationSuggestions, setDestinationSuggestions] = useState<string[]>(
    DESTINATION_SUGGESTIONS.slice(0, 6),
  );
  const [fromFocused, setFromFocused] = useState(false);
  const [fromSuggestions, setFromSuggestions] = useState<string[]>(
    FROM_CITY_SUGGESTIONS.slice(0, 6),
  );
  const [styleFocused, setStyleFocused] = useState(false);
  const [budgetFocused, setBudgetFocused] = useState(false);

  const STYLE_OPTIONS = ["Budget", "Moderate", "Luxury", "Family-friendly", "Adventure", "Food-focused"];
  const BUDGET_OPTIONS = ["$1000–$1500", "$1500–$2500", "$2500–$4000", "$4000+", "$250/night+", "Luxury no strict cap"];

  const styleSuggestions = snapshotInput.style
    ? STYLE_OPTIONS.filter((v) => v.toLowerCase().includes(snapshotInput.style.toLowerCase()))
    : STYLE_OPTIONS;
  const budgetSuggestions = snapshotInput.budget
    ? BUDGET_OPTIONS.filter((v) => v.toLowerCase().includes(snapshotInput.budget.toLowerCase()))
    : BUDGET_OPTIONS;

  const startDateObj = toDate(snapshotInput.startDate);
  const endDateObj = toDate(snapshotInput.endDate);

  const latestFlights = useMemo(
    () => (flightResults.length > 0 ? flightResults[flightResults.length - 1] : null),
    [flightResults],
  );
  const latestHotels = useMemo(
    () => (hotelResults.length > 0 ? hotelResults[hotelResults.length - 1] : null),
    [hotelResults],
  );
  const dedupedLatestFlightCards = useMemo(() => {
    if (!latestFlights) return [];
    // De-duplicate by itinerary signature and keep the cheapest fare.
    const byItinerary = new Map<string, FlightCard>();
    for (const card of latestFlights.cards) {
      const key = [
        card.airline.trim().toLowerCase(),
        card.departure.code.trim().toUpperCase(),
        card.departure.time.trim(),
        card.arrival.code.trim().toUpperCase(),
        card.arrival.time.trim(),
        card.duration.trim().toLowerCase(),
        card.stops,
      ].join("|");
      const existing = byItinerary.get(key);
      if (!existing || card.price < existing.price) {
        byItinerary.set(key, card);
      }
    }
    return Array.from(byItinerary.values());
  }, [latestFlights]);

  const localDestinationSuggestions = useMemo(() => {
    const q = snapshotInput.destination.trim().toLowerCase();
    if (!q) return DESTINATION_SUGGESTIONS.slice(0, 6);
    const starts = DESTINATION_SUGGESTIONS.filter((v) => v.toLowerCase().startsWith(q));
    const contains = DESTINATION_SUGGESTIONS.filter(
      (v) => !starts.includes(v) && v.toLowerCase().includes(q),
    );
    return [...starts, ...contains].slice(0, 6);
  }, [snapshotInput.destination]);

  const localFromSuggestions = useMemo(() => {
    const q = snapshotInput.from.trim().toLowerCase();
    if (!q) return FROM_CITY_SUGGESTIONS.slice(0, 6);
    const starts = FROM_CITY_SUGGESTIONS.filter((v) => v.toLowerCase().startsWith(q));
    const contains = FROM_CITY_SUGGESTIONS.filter(
      (v) => !starts.includes(v) && v.toLowerCase().includes(q),
    );
    return [...starts, ...contains].slice(0, 6);
  }, [snapshotInput.from]);

  // Live Nominatim lookup for destination
  useEffect(() => {
    const q = snapshotInput.destination.trim();
    if (!q || q.length < 2) {
      setDestinationSuggestions(localDestinationSuggestions);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=6&q=${encodeURIComponent(q)}`;
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) throw new Error("lookup failed");
        const rows: NominatimRow[] = await res.json();
        const ranked = rankPlaceSuggestions(rows, q, localDestinationSuggestions);
        setDestinationSuggestions(ranked.length > 0 ? ranked : localDestinationSuggestions);
      } catch {
        setDestinationSuggestions(localDestinationSuggestions);
      }
    }, 250);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [snapshotInput.destination, localDestinationSuggestions]);

  // Live Nominatim lookup for from-city
  useEffect(() => {
    const q = snapshotInput.from.trim();
    if (!q || q.length < 2) {
      setFromSuggestions(localFromSuggestions);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=6&q=${encodeURIComponent(q)}`;
        const res = await fetch(url, { signal: controller.signal });
        if (!res.ok) throw new Error("lookup failed");
        const rows: NominatimRow[] = await res.json();
        const ranked = rankPlaceSuggestions(rows, q, localFromSuggestions);
        setFromSuggestions(ranked.length > 0 ? ranked : localFromSuggestions);
      } catch {
        setFromSuggestions(localFromSuggestions);
      }
    }, 250);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [snapshotInput.from, localFromSuggestions]);

  // Sync snapshot from profile (agent → UI)
  useEffect(() => {
    setSnapshotInput((prev) => ({
      ...prev,
      destination: profile?.destinations || prev.destination,
      from: profile?.flight_departure || prev.from,
      travelers: profile?.num_travelers ? String(profile.num_travelers) : prev.travelers,
      style: profile?.travel_style || prev.style,
      budget: profile?.budget_estimate || prev.budget,
      startDate: profile?.flight_outbound_ymd || prev.startDate,
      endDate: profile?.flight_return_ymd || prev.endDate,
    }));
  }, [profile]);

  // Debounced sync: snapshot UI → backend profile (so the agent knows what's filled in)
  useEffect(() => {
    const sid =
      sessionId ||
      (typeof window !== "undefined"
        ? window.sessionStorage.getItem("wayfarer_session_id") || ""
        : "");
    if (!sid) return;
    const fields = {
      destinations: snapshotInput.destination || undefined,
      flight_departure: snapshotInput.from || undefined,
      num_travelers: snapshotInput.travelers ? parseInt(snapshotInput.travelers, 10) || undefined : undefined,
      travel_style: snapshotInput.style || undefined,
      budget_estimate: snapshotInput.budget || undefined,
      flight_outbound_ymd: snapshotInput.startDate || undefined,
      flight_return_ymd: snapshotInput.endDate || undefined,
    };
    // Only sync if at least one field is set
    const hasAny = Object.values(fields).some((v) => v !== undefined);
    if (!hasAny) return;

    const timer = setTimeout(() => {
      syncProfile(sid, fields);
    }, 200);
    return () => clearTimeout(timer);
  }, [
    sessionId,
    snapshotInput.destination,
    snapshotInput.from,
    snapshotInput.travelers,
    snapshotInput.style,
    snapshotInput.budget,
    snapshotInput.startDate,
    snapshotInput.endDate,
  ]);

  const dateButtonText =
    snapshotInput.startDate && snapshotInput.endDate
      ? `${snapshotInput.startDate} → ${snapshotInput.endDate}`
      : snapshotInput.startDate
        ? snapshotInput.startDate
        : "Select dates";

  const openDatePicker = () => {
    if (dateButtonRef.current) {
      const rect = dateButtonRef.current.getBoundingClientRect();
      const POPOVER_W = 580;
      const left = Math.min(rect.left, window.innerWidth - POPOVER_W - 16);
      setCalendarAnchor({ top: rect.bottom + 8, left: Math.max(8, left) });
    }
    setDatePickerOpen(true);
  };

  const closeDatePicker = () => setDatePickerOpen(false);

  const pickDate = (picked: Date) => {
    if (!startDateObj || (startDateObj && endDateObj)) {
      setSnapshotInput((prev) => ({ ...prev, startDate: toYmd(picked), endDate: "" }));
      return;
    }
    if (picked.getTime() < startDateObj.getTime()) {
      setSnapshotInput((prev) => ({
        ...prev,
        startDate: toYmd(picked),
        endDate: toYmd(startDateObj),
      }));
    } else {
      setSnapshotInput((prev) => ({ ...prev, endDate: toYmd(picked) }));
    }
    closeDatePicker();
  };

  const meta = SECTION_META[activeSection];

  return (
    <div className="flex flex-col gap-4">
      {/* ── Trip Snapshot card ───────────────────────────────── */}
      <div className="rounded-2xl border border-black/[0.05] bg-white shadow-card p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs font-semibold uppercase tracking-widest text-stone-400">
            Trip Snapshot
          </p>
          <button
            type="button"
            onClick={onOpenChat}
            className="text-[11px] font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-0.5 transition-colors"
          >
            Chat with Wayfarer
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" className="w-3 h-3 ml-0.5" aria-hidden>
              <path d="M8.25 4.5l7.5 7.5-7.5 7.5" />
            </svg>
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-2">
          {/* Destination */}
          <SnapshotField label="Destination">
            <AutoInput
              value={snapshotInput.destination}
              onChange={(v) => setSnapshotInput((prev) => ({ ...prev, destination: v }))}
              placeholder="e.g. Tokyo, Japan"
              suggestions={destinationSuggestions}
              focused={destinationFocused}
              onFocus={() => setDestinationFocused(true)}
              onBlur={() => setTimeout(() => setDestinationFocused(false), 100)}
            />
          </SnapshotField>

          {/* From */}
          <SnapshotField label="Flying from">
            <AutoInput
              value={snapshotInput.from}
              onChange={(v) => setSnapshotInput((prev) => ({ ...prev, from: v }))}
              placeholder="e.g. Los Angeles"
              suggestions={fromSuggestions}
              focused={fromFocused}
              onFocus={() => setFromFocused(true)}
              onBlur={() => setTimeout(() => setFromFocused(false), 100)}
            />
          </SnapshotField>

          {/* Dates */}
          <div className="flex flex-col gap-1 rounded-xl border border-black/[0.04] bg-stone-50/60 px-3 py-2.5">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-stone-400">
              Dates
            </p>
            <button
              ref={dateButtonRef}
              type="button"
              onClick={openDatePicker}
              className="text-sm font-medium text-stone-800 text-left hover:text-indigo-600 transition-colors truncate"
            >
              {dateButtonText}
            </button>
          </div>

          {/* Travelers */}
          <SnapshotField label="Travelers">
            <input
              type="number"
              min={1}
              max={20}
              value={snapshotInput.travelers}
              onChange={(e) =>
                setSnapshotInput((prev) => ({ ...prev, travelers: e.target.value }))
              }
              placeholder="1"
              className="w-full text-sm font-medium text-stone-800 bg-transparent outline-none placeholder:text-stone-400"
            />
          </SnapshotField>

          {/* Style */}
          {/* Style */}
          <SnapshotField label="Travel style">
            <AutoInput
              value={snapshotInput.style}
              onChange={(v) => setSnapshotInput((prev) => ({ ...prev, style: v }))}
              placeholder="e.g. Luxury"
              suggestions={styleSuggestions}
              focused={styleFocused}
              onFocus={() => setStyleFocused(true)}
              onBlur={() => setTimeout(() => setStyleFocused(false), 100)}
            />
          </SnapshotField>

          {/* Budget */}
          <SnapshotField label="Budget target">
            <AutoInput
              value={snapshotInput.budget}
              onChange={(v) => setSnapshotInput((prev) => ({ ...prev, budget: v }))}
              placeholder="e.g. $2500 total"
              suggestions={budgetSuggestions}
              focused={budgetFocused}
              onFocus={() => setBudgetFocused(true)}
              onBlur={() => setTimeout(() => setBudgetFocused(false), 100)}
            />
          </SnapshotField>
        </div>

        {/* Helper note */}
        <p className="mt-3 text-[11px] text-stone-400 leading-snug">
          Not sure about some details yet? That&apos;s totally fine —{" "}
          <button
            type="button"
            onClick={onOpenChat}
            className="text-indigo-600 hover:text-indigo-700 font-medium transition-colors"
          >
            open a chat with Wayfarer
          </button>{" "}
          and figure it out together.
        </p>
      </div>

      {/* ── Calendar portal (rendered into document.body to escape overflow/z-index) ── */}
      {datePickerOpen &&
        calendarAnchor &&
        typeof document !== "undefined" &&
        createPortal(
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 z-[998]"
              onClick={closeDatePicker}
              aria-hidden
            />
            {/* Popover */}
            <div
              className="fixed z-[999] w-[580px] max-w-[calc(100vw-2rem)] rounded-2xl border border-black/[0.07] bg-white p-4 shadow-float"
              style={{ top: calendarAnchor.top, left: calendarAnchor.left }}
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-xs font-semibold text-stone-500">
                  Select departure and return
                </span>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    className="w-7 h-7 rounded-lg border border-black/[0.07] bg-stone-50 flex items-center justify-center text-stone-500 hover:bg-stone-100 transition-colors"
                    onClick={() => setCalendarMonth((m) => addMonths(m, -1))}
                    aria-label="Previous month"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
                      <path d="M15.75 19.5L8.25 12l7.5-7.5" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    className="w-7 h-7 rounded-lg border border-black/[0.07] bg-stone-50 flex items-center justify-center text-stone-500 hover:bg-stone-100 transition-colors"
                    onClick={() => setCalendarMonth((m) => addMonths(m, 1))}
                    aria-label="Next month"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-3.5 h-3.5" aria-hidden>
                      <path d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                    </svg>
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-5">
                {[calendarMonth, addMonths(calendarMonth, 1)].map((monthBase) => {
                  const label = monthBase.toLocaleDateString(undefined, {
                    month: "long",
                    year: "numeric",
                  });
                  const cells = buildMonthGrid(monthBase);
                  return (
                    <div key={label}>
                      <p className="text-xs font-semibold text-stone-700 mb-2">{label}</p>
                      <div className="grid grid-cols-7 gap-0.5 text-[10px] text-stone-400 mb-1">
                        {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                          <span key={`${label}-${d}-${i}`} className="text-center py-0.5 font-medium">
                            {d}
                          </span>
                        ))}
                      </div>
                      <div className="grid grid-cols-7 gap-0.5">
                        {cells.map((day, idx) => {
                          if (!day) return <span key={`${label}-pad-${idx}`} className="h-8" />;
                          const isStart = !!startDateObj && sameDay(day, startDateObj);
                          const isEnd = !!endDateObj && sameDay(day, endDateObj);
                          const inMid =
                            !!startDateObj &&
                            !!endDateObj &&
                            inDateRange(day, startDateObj, endDateObj) &&
                            !isStart &&
                            !isEnd;
                          return (
                            <button
                              key={`${label}-${idx}`}
                              type="button"
                              onClick={() => pickDate(day)}
                              className={`h-8 rounded-full text-xs font-medium transition-colors ${
                                isStart || isEnd
                                  ? "bg-indigo-600 text-white"
                                  : inMid
                                    ? "bg-indigo-100 text-indigo-700"
                                    : "text-stone-700 hover:bg-stone-100"
                              }`}
                            >
                              {day.getDate()}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-4 flex items-center justify-end gap-3 border-t border-black/[0.05] pt-3">
                {(snapshotInput.startDate || snapshotInput.endDate) && (
                  <button
                    type="button"
                    className="text-xs font-medium text-stone-500 hover:text-stone-700 transition-colors"
                    onClick={() =>
                      setSnapshotInput((prev) => ({ ...prev, startDate: "", endDate: "" }))
                    }
                  >
                    Clear
                  </button>
                )}
                <button
                  type="button"
                  className="flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors"
                  onClick={closeDatePicker}
                >
                  Done
                </button>
              </div>
            </div>
          </>,
          document.body,
        )}

      {/* ── Active section card ──────────────────────────────── */}
      <div className="rounded-2xl border border-black/[0.05] bg-white shadow-card p-4">
        {/* Section header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-lg flex items-center justify-center ${meta.color}`}
              aria-hidden
            >
              <span className="text-[13px]">
                {activeSection === "flights"
                  ? "✈️"
                  : activeSection === "hotels"
                    ? "🏨"
                    : activeSection === "itinerary"
                      ? "🗓️"
                      : activeSection === "transportation"
                        ? "🚆"
                        : activeSection === "budget"
                          ? "💰"
                          : activeSection === "packing"
                            ? "🎒"
                            : "🛂"}
              </span>
            </div>
            <p className="text-xs font-semibold uppercase tracking-widest text-stone-400">
              {meta.label}
            </p>
          </div>

          {/* Section status chip */}
          {activeSection === "flights" && latestFlights && !savedFlight && (
            <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold bg-blue-50 text-blue-700 border-blue-200">
              {dedupedLatestFlightCards.length} options
            </span>
          )}
          {activeSection === "flights" && savedFlight && (
            <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-700 border-emerald-200">
              Saved
            </span>
          )}
          {activeSection === "hotels" && latestHotels && !savedHotel && (
            <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold bg-blue-50 text-blue-700 border-blue-200">
              {latestHotels.cards.length} options
            </span>
          )}
          {activeSection === "hotels" && savedHotel && (
            <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold bg-emerald-100 text-emerald-700 border-emerald-200">
              Saved
            </span>
          )}
        </div>

        {/* ── Flights ── */}
        {activeSection === "flights" && (
          <>
            {latestFlights ? (
              <div className="flex flex-col gap-2">
                <p className="text-[11px] text-stone-400 mb-1">{latestFlights.label}</p>
                {latestFlights.cards.length > dedupedLatestFlightCards.length && (
                  <p className="text-[10px] text-stone-400 -mt-1">
                    Removed duplicate itineraries and kept the best-priced fare for each route.
                  </p>
                )}

                {savedFlight ? (
                  <>
                    <FlightRow card={savedFlight} saved />
                    <button
                      type="button"
                      onClick={() => setSavedFlight(null)}
                      className="text-[11px] font-medium text-indigo-600 hover:text-indigo-700 transition-colors self-start"
                    >
                      Change selected flight
                    </button>
                  </>
                ) : (
                  dedupedLatestFlightCards.slice(0, 6).map((card, i) => (
                    <FlightRow
                      key={`${card.airline}-${card.price}-${i}`}
                      card={card}
                      onSave={(next) => setSavedFlight(next)}
                    />
                  ))
                )}
              </div>
            ) : (
              <EmptyState
                text="Flight options will appear here after a search."
                onOpenChat={onOpenChat}
              />
            )}
          </>
        )}

        {/* ── Hotels ── */}
        {activeSection === "hotels" && (
          <>
            {latestHotels ? (
              <div className="flex flex-col gap-2">
                <p className="text-[11px] text-stone-400 mb-1">{latestHotels.label}</p>

                {savedHotel ? (
                  <>
                    <HotelRow card={savedHotel} saved />
                    <button
                      type="button"
                      onClick={() => setSavedHotel(null)}
                      className="text-[11px] font-medium text-indigo-600 hover:text-indigo-700 transition-colors self-start"
                    >
                      Change selected hotel
                    </button>
                  </>
                ) : (
                  latestHotels.cards.slice(0, 6).map((card, i) => (
                    <HotelRow
                      key={`${card.name}-${card.price_per_night}-${i}`}
                      card={card}
                      onSave={(next) => setSavedHotel(next)}
                    />
                  ))
                )}
              </div>
            ) : (
              <EmptyState
                text="Hotel options will appear here after a search."
                onOpenChat={onOpenChat}
              />
            )}
          </>
        )}

        {/* ── Other sections ── */}
        {!["flights", "hotels"].includes(activeSection) && (
          <EmptyState text={meta.description} onOpenChat={onOpenChat} />
        )}
      </div>
    </div>
  );
}

function EmptyState({
  text,
  onOpenChat,
}: {
  text: string;
  onOpenChat?: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8">
      <p className="text-sm text-stone-400 text-center max-w-xs leading-relaxed">{text}</p>
      {onOpenChat && (
        <button
          type="button"
          onClick={onOpenChat}
          className="flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors"
        >
          Ask Wayfarer
        </button>
      )}
    </div>
  );
}
