"use client";

import { motion } from "framer-motion";
import type { CardsData, FlightCard, HotelCard } from "@/lib/types";

interface CardsPanelProps {
  data: CardsData;
  onClose: () => void;
}

function StopLine({ stops }: { stops: number }) {
  if (stops === 0) return <span className="text-xs text-emerald-600 font-medium">Nonstop</span>;
  return <span className="text-xs text-amber-600">{stops} stop{stops > 1 ? "s" : ""}</span>;
}

function FlightCardItem({ card, index }: { card: FlightCard; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.25 }}
      className="bg-white/80 backdrop-blur-sm border border-white/70 rounded-2xl p-4 shadow-sm hover:shadow-md hover:bg-white transition-all duration-200 group"
    >
      {/* Airline + price row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {card.airline_logo && (
            <img
              src={card.airline_logo}
              alt={card.airline}
              className="h-4 w-auto object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          )}
          <span className="text-sm font-semibold text-gray-800 truncate max-w-[140px]">{card.airline}</span>
        </div>
        <span className="text-xl font-bold text-indigo-600">${card.price}</span>
      </div>

      {/* Route row */}
      <div className="flex items-center gap-2">
        <div className="text-center min-w-[48px]">
          <div className="text-base font-bold text-gray-900 tabular-nums">{card.departure.time}</div>
          <div className="text-[11px] font-medium text-gray-500">{card.departure.code}</div>
        </div>

        <div className="flex-1 flex flex-col items-center gap-0.5">
          <div className="text-[10px] text-gray-400">{card.duration}</div>
          <div className="w-full flex items-center gap-1">
            <div className="h-px flex-1 bg-gray-200" />
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"
              className="w-3 h-3 text-indigo-400 flex-shrink-0">
              <path d="M3.478 2.405a.75.75 0 00-.926.94l2.432 7.905H13.5a.75.75 0 010 1.5H4.984l-2.432 7.905a.75.75 0 00.926.94 60.519 60.519 0 0018.445-8.986.75.75 0 000-1.218A60.517 60.517 0 003.478 2.405z" />
            </svg>
            <div className="h-px flex-1 bg-gray-200" />
          </div>
          <StopLine stops={card.stops} />
        </div>

        <div className="text-center min-w-[48px]">
          <div className="text-base font-bold text-gray-900 tabular-nums">{card.arrival.time}</div>
          <div className="text-[11px] font-medium text-gray-500">{card.arrival.code}</div>
        </div>
      </div>

      {/* Footer — two sibling links, never nested */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
        <span className="text-[10px] text-gray-400">Economy · per person</span>
        <div className="flex items-center gap-2">
          <a
            href={card.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs font-medium text-indigo-600 hover:text-indigo-700 flex items-center gap-0.5 transition-colors"
          >
            Google Flights
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
              <path fillRule="evenodd" d="M5.22 14.78a.75.75 0 001.06 0l7.22-7.22v5.69a.75.75 0 001.5 0v-7.5a.75.75 0 00-.75-.75h-7.5a.75.75 0 000 1.5h5.69l-7.22 7.22a.75.75 0 000 1.06z" clipRule="evenodd" />
            </svg>
          </a>
        </div>
      </div>
    </motion.div>
  );
}

function StarRow({ rating }: { rating: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <svg key={i} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"
          fill={i < Math.round(rating) ? "#f59e0b" : "#e5e7eb"}
          className="w-3 h-3">
          <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" />
        </svg>
      ))}
    </div>
  );
}

function HotelCardItem({ card, index }: { card: HotelCard; index: number }) {
  return (
    <motion.a
      href={card.link ?? "#"}
      target="_blank"
      rel="noopener noreferrer"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06, duration: 0.25 }}
      className="block bg-white/80 backdrop-blur-sm border border-white/70 rounded-2xl overflow-hidden shadow-sm hover:shadow-md hover:bg-white transition-all duration-200 group cursor-pointer"
    >
      {card.image && (
        <img
          src={card.image}
          alt={card.name}
          className="w-full h-28 object-cover"
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      )}

      <div className="p-4">
        {/* Name + price */}
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-800 leading-tight truncate">{card.name}</h3>
            {card.hotel_class && (
              <p className="text-[10px] text-gray-400 mt-0.5">{card.hotel_class}</p>
            )}
          </div>
          <div className="text-right flex-shrink-0">
            {card.price_per_night && card.price_per_night !== "N/A" ? (
              <>
                <div className="text-lg font-bold text-indigo-600">{card.price_per_night}</div>
                <div className="text-[10px] text-gray-400">/ night</div>
              </>
            ) : (
              <div className="text-[10px] text-gray-400 mt-1">See site</div>
            )}
          </div>
        </div>

        {/* Rating */}
        {card.rating !== undefined && (
          <div className="flex items-center gap-1.5 mb-2">
            <StarRow rating={card.rating} />
            <span className="text-xs font-medium text-gray-700">{card.rating}</span>
            {card.reviews && (
              <span className="text-[10px] text-gray-400">({card.reviews.toLocaleString()})</span>
            )}
          </div>
        )}

        {/* Free cancellation badge */}
        {card.free_cancellation && (
          <div className="inline-flex items-center gap-1 text-[10px] text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-0.5 mb-2">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
            </svg>
            Free cancellation
          </div>
        )}

        {/* Amenities */}
        {card.amenities.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {card.amenities.slice(0, 4).map((a) => (
              <span key={a} className="text-[10px] text-gray-500 bg-gray-100 rounded-full px-2 py-0.5">{a}</span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-gray-100">
          {card.total_price && (
            <span className="text-[10px] text-gray-400">Total: {card.total_price}</span>
          )}
          <span className="ml-auto text-xs font-medium text-indigo-600 group-hover:text-indigo-700 flex items-center gap-0.5">
            View
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3 h-3">
              <path fillRule="evenodd" d="M5.22 14.78a.75.75 0 001.06 0l7.22-7.22v5.69a.75.75 0 001.5 0v-7.5a.75.75 0 00-.75-.75h-7.5a.75.75 0 000 1.5h5.69l-7.22 7.22a.75.75 0 000 1.06z" clipRule="evenodd" />
            </svg>
          </span>
        </div>
      </div>
    </motion.a>
  );
}

export default function CardsPanel({ data, onClose }: CardsPanelProps) {
  const isFlights = data.kind === "flights";
  const count = data.cards.length;
  const title = isFlights
    ? `${count} Flight${count !== 1 ? "s" : ""} Found`
    : `${count} Hotel${count !== 1 ? "s" : ""} Found`;

  return (
    <div
      className="h-full flex flex-col rounded-3xl overflow-hidden border border-white/60 shadow-2xl shadow-indigo-200/40"
      style={{ background: "rgba(255,255,255,0.72)" }}
    >
      {/* Header — same gradient as chat header */}
      <header className="flex-shrink-0 bg-gradient-to-r from-indigo-600 via-violet-600 to-purple-700 px-4 py-4 flex items-center justify-between shadow-lg shadow-indigo-900/20">
        <div className="flex items-center gap-2">
          <span className="text-lg">{isFlights ? "✈️" : "🏨"}</span>
          <div>
            <h2 className="text-sm font-bold text-white">{title}</h2>
            <p className="text-indigo-200 text-xs">{data.label}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          title="Close panel"
          className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 flex items-center justify-center transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="white" className="w-3.5 h-3.5">
            <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
          </svg>
        </button>
      </header>

      {/* Scrollable cards list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 chat-scroll">
        {isFlights
          ? (data.cards as FlightCard[]).map((card, i) => (
              <FlightCardItem
                key={`${card.airline}-${card.departure.code}-${card.arrival.code}-${card.departure.time}-${card.price}-${i}`}
                card={card}
                index={i}
              />
            ))
          : (data.cards as HotelCard[]).map((card, i) => (
              <HotelCardItem key={i} card={card} index={i} />
            ))}
      </div>
    </div>
  );
}
