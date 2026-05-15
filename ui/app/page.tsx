"use client";

import { useState } from "react";
import ChatWindow from "@/components/ChatWindow";
import PlannerWorkspace from "@/components/PlannerWorkspace";
import type { FlightCard, HotelCard, TripProfileSnapshot } from "@/lib/types";

export type SectionKey =
  | "flights"
  | "hotels"
  | "itinerary"
  | "transportation"
  | "budget"
  | "packing"
  | "advisory";

const NAV_SECTIONS: Array<{ key: SectionKey; label: string }> = [
  { key: "flights", label: "Flights" },
  { key: "hotels", label: "Hotels" },
  { key: "itinerary", label: "Itinerary" },
  { key: "transportation", label: "Transportation" },
  { key: "budget", label: "Budget" },
  { key: "packing", label: "Packing" },
  { key: "advisory", label: "Advisory" },
];

function NavIcon({ type }: { type: SectionKey }) {
  const props = {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "w-4 h-4 shrink-0",
    "aria-hidden": true,
  };
  switch (type) {
    case "flights":
      return (
        <svg {...props}>
          <path d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
        </svg>
      );
    case "hotels":
      return (
        <svg {...props}>
          <path d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />
        </svg>
      );
    case "itinerary":
      return (
        <svg {...props}>
          <path d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zm2.25-4.5h.008v.008H16.5v-.008zm0 2.25h.008v.008H16.5V15z" />
        </svg>
      );
    case "transportation":
      return (
        <svg {...props}>
          <path d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
        </svg>
      );
    case "budget":
      return (
        <svg {...props}>
          <path d="M2.25 18.75a60.07 60.07 0 0115.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 013 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 00-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 01-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 003 15h-.75M15 10.5a3 3 0 11-6 0 3 3 0 016 0zm3 0h.008v.008H18V10.5zm-12 0h.008v.008H6V10.5z" />
        </svg>
      );
    case "packing":
      return (
        <svg {...props}>
          <path d="M15.75 10.5V6a3.75 3.75 0 10-7.5 0v4.5m11.356-1.993l1.263 12c.07.665-.45 1.243-1.119 1.243H4.25a1.125 1.125 0 01-1.12-1.243l1.264-12A1.125 1.125 0 015.513 7.5h12.974c.576 0 1.059.435 1.119 1.007zM8.625 10.5a.375.375 0 11-.75 0 .375.375 0 01.75 0zm7.5 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" />
        </svg>
      );
    case "advisory":
      return (
        <svg {...props}>
          <path d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
      );
  }
}

export default function Home() {
  const [activeSection, setActiveSection] = useState<SectionKey>("flights");
  const [chatWidth, setChatWidth] = useState(400);
  const [chatOpen, setChatOpen] = useState(true);
  const [resizing, setResizing] = useState(false);
  const [flightResults, setFlightResults] = useState<
    Array<{ label: string; cards: FlightCard[] }>
  >([]);
  const [hotelResults, setHotelResults] = useState<
    Array<{ label: string; cards: HotelCard[] }>
  >([]);
  const [profile, setProfile] = useState<TripProfileSnapshot | null>(null);
  const [sessionId, setSessionId] = useState<string>("");

  const beginResize = (startX: number, startWidth: number) => {
    setResizing(true);
    const onMove = (e: MouseEvent) => {
      const delta = startX - e.clientX;
      const next = Math.min(600, Math.max(320, startWidth + delta));
      setChatWidth(next);
    };
    const onUp = () => {
      setResizing(false);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  const hasFlights = flightResults.length > 0;
  const hasHotels = hotelResults.length > 0;

  return (
    <div className="flex h-screen bg-canvas overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside className="w-52 shrink-0 flex flex-col h-full bg-white border-r border-black/[0.05] py-5 px-3">
        {/* Brand */}
        <div className="flex items-center gap-2 px-2 mb-6">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-brand">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="white"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="w-4 h-4"
              aria-hidden
            >
              <path d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </div>
          <span className="text-sm font-bold text-stone-800 tracking-tight">
            Wayfarer
          </span>
        </div>

        {/* Section label */}
        <p className="text-xs font-semibold uppercase tracking-widest text-stone-400 px-2 mb-1.5">
          Plan
        </p>

        {/* Nav items */}
        <nav className="flex flex-col gap-0.5" aria-label="Planning sections">
          {NAV_SECTIONS.map(({ key, label }) => {
            const isActive = activeSection === key;
            const hasData =
              key === "flights"
                ? hasFlights
                : key === "hotels"
                  ? hasHotels
                  : false;
            return (
              <button
                key={key}
                onClick={() => setActiveSection(key)}
                className={`flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors text-left w-full ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-brand"
                    : "text-stone-500 hover:bg-stone-100 hover:text-stone-800"
                }`}
              >
                <NavIcon type={key} />
                <span className="flex-1 truncate">{label}</span>
                {hasData && !isActive && (
                  <span
                    className="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"
                    aria-label="has data"
                  />
                )}
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="mt-auto border-t border-black/[0.05] pt-4">
          <p className="text-[10px] text-stone-400 px-2 text-center leading-snug">
            AI-powered travel planning
          </p>
        </div>
      </aside>

      {/* ── Main column ─────────────────────────────────────── */}
      <div
        className="flex-1 min-w-0 flex flex-col overflow-hidden transition-[padding-right] duration-300"
        style={{ paddingRight: chatOpen ? chatWidth : 0 }}
      >
        {/* TopBar */}
        <header className="h-14 flex items-center justify-between px-6 bg-white border-b border-black/[0.05] shrink-0">
          <div>
            <p className="text-sm font-bold text-stone-800">
              {profile?.destinations ? profile.destinations : "Trip Planner"}
            </p>
            <p className="text-[11px] text-stone-400 mt-0.5">
              {profile?.destinations
                ? [
                    profile.flight_outbound_ymd,
                    profile.flight_return_ymd,
                  ]
                    .filter(Boolean)
                    .join(" → ") || "Dates not set"
                : "Organize your trip details below"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {!chatOpen && (
              <button
                onClick={() => setChatOpen(true)}
                className="flex items-center gap-1.5 rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors"
                aria-label="Open chat"
              >
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
                  <path d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                </svg>
                Open Chat
              </button>
            )}
          </div>
        </header>

        {/* Scrollable content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin px-5 py-5">
          <div className="max-w-3xl mx-auto flex flex-col gap-4">
            <PlannerWorkspace
              activeSection={activeSection}
              onSectionChange={setActiveSection}
              flightResults={flightResults}
              hotelResults={hotelResults}
              profile={profile}
              sessionId={sessionId}
              onOpenChat={() => setChatOpen(true)}
            />
          </div>
        </main>
      </div>

      {/* ── Chat drawer ─────────────────────────────────────── */}
      <div
        className="absolute inset-y-0 right-0 flex transition-transform duration-300 z-20"
        style={{
          width: chatWidth,
          transform: chatOpen
            ? "translateX(0)"
            : `translateX(${chatWidth}px)`,
        }}
      >
        {/* Resize handle */}
        <div
          className={`w-1 h-full cursor-col-resize shrink-0 border-l border-black/[0.05] ${
            chatOpen ? "hover:bg-indigo-200/60" : "bg-transparent"
          } ${resizing ? "bg-indigo-300/70" : ""}`}
          onMouseDown={(e) => chatOpen && beginResize(e.clientX, chatWidth)}
          aria-label="Resize chat panel"
          role="separator"
        />

        {/* Chat panel */}
        <div className="flex-1 bg-white flex flex-col overflow-hidden shadow-float">
          <ChatWindow
            onClose={() => setChatOpen(false)}
            onSessionId={(id) => setSessionId(id)}
            onCards={(data) => {
              if (!data) {
                setFlightResults([]);
                setHotelResults([]);
                return;
              }
              if (data.kind === "flights") {
                setFlightResults((prev) => [
                  ...prev,
                  { label: data.label, cards: data.cards },
                ]);
              } else {
                setHotelResults((prev) => [
                  ...prev,
                  { label: data.label, cards: data.cards },
                ]);
              }
            }}
            onProfile={(p) => setProfile(p)}
            onSessionReset={() => setProfile(null)}
          />
        </div>
      </div>
    </div>
  );
}
