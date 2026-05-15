"use client";

import { motion } from "framer-motion";

export type MessageRole = "user" | "assistant" | "tool";

export interface ToolUsed {
  tool: string;
  label: string;
}

export interface MessageData {
  id: string;
  role: MessageRole;
  content: string;
  label?: string;
  timestamp: Date;
  suggestions?: string[];
  toolsUsed?: ToolUsed[];
  memorySaved?: string[];
}

interface MessageProps {
  message: MessageData;
  showSuggestions?: boolean;
  onSuggestion?: (text: string) => void;
}

const TOOL_ICONS: Record<string, string> = {
  search_flights: "✈️",
  search_hotels: "🏨",
  plan_itinerary: "🗓️",
  estimate_budget: "💰",
  suggest_packing_list: "🎒",
  get_travel_advisory: "🛂",
  get_transportation_guide: "🚆",
  generate_trip_report: "📋",
};

function ToolIndicator({ message }: { message: MessageData }) {
  const icon = TOOL_ICONS[message.content] ?? "🔧";
  const label = message.label ?? message.content.replace(/_/g, " ");

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-2 pl-10"
    >
      <span className="inline-flex items-center gap-1.5 text-[11px] text-indigo-600 bg-indigo-50 border border-indigo-100 rounded-full px-2.5 py-1">
        <span>{icon}</span>
        <span>{label}…</span>
        <span className="flex gap-0.5 ml-0.5">
          <span className="bounce-dot w-1 h-1 rounded-full bg-indigo-400 inline-block" />
          <span className="bounce-dot w-1 h-1 rounded-full bg-indigo-400 inline-block" />
          <span className="bounce-dot w-1 h-1 rounded-full bg-indigo-400 inline-block" />
        </span>
      </span>
    </motion.div>
  );
}

function formatContent(content: string) {
  const parts = content.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part.split("\n").map((line, j, arr) => (
      <span key={`${i}-${j}`}>
        {line}
        {j < arr.length - 1 && <br />}
      </span>
    ));
  });
}

export default function Message({
  message,
  showSuggestions = false,
  onSuggestion,
}: MessageProps) {
  if (message.role === "tool") {
    return <ToolIndicator message={message} />;
  }

  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: [0.25, 0.46, 0.45, 0.94] }}
      className={`flex flex-col ${isUser ? "items-end" : "items-start"} gap-1.5`}
    >
      {/* Tool badges */}
      {!isUser && message.toolsUsed && message.toolsUsed.length > 0 && (
        <div className="flex flex-wrap gap-1 pl-10">
          {message.toolsUsed.map(({ tool, label }) => {
            const icon = TOOL_ICONS[tool] ?? "🔧";
            return (
              <span
                key={tool}
                className="inline-flex items-center gap-1 text-[10px] text-stone-400 bg-stone-50 border border-black/[0.05] rounded-full px-2 py-0.5"
              >
                <span>{icon}</span>
                <span>{label}</span>
              </span>
            );
          })}
        </div>
      )}

      {/* Memory saved badge */}
      {!isUser && message.memorySaved && message.memorySaved.length > 0 && (
        <div className="flex flex-wrap gap-1 pl-10">
          <span className="inline-flex items-center gap-1 text-[10px] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-full px-2 py-0.5">
            <span>💾</span>
            <span>
              Saved to memory:{" "}
              {message.memorySaved.map((f) => f.replace(/_/g, " ")).join(", ")}
            </span>
          </span>
        </div>
      )}

      {/* Bubble row */}
      <div className={`flex items-end gap-2 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
        {/* Avatar */}
        <div
          className={`flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white ring-2 ring-white ${
            isUser ? "bg-violet-400" : "bg-gradient-to-br from-indigo-500 to-violet-600"
          }`}
        >
          {isUser ? "You" : "W"}
        </div>

        {/* Bubble */}
        <div
          className={`max-w-[78%] px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-indigo-600 text-white rounded-br-sm"
              : "bg-stone-100 text-stone-800 rounded-bl-sm border border-black/[0.04]"
          }`}
        >
          <p className="whitespace-pre-wrap">{formatContent(message.content)}</p>
          <p
            suppressHydrationWarning
            className={`text-[10px] mt-1 ${isUser ? "text-indigo-200 text-right" : "text-stone-400"}`}
          >
            {message.timestamp.getTime() === 0
              ? "\u00A0"
              : message.timestamp.toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
          </p>
        </div>
      </div>

      {/* Quick-reply chips */}
      {!isUser && showSuggestions && message.suggestions && message.suggestions.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.1 }}
          className="flex flex-wrap gap-1.5 pl-9"
        >
          {message.suggestions.map((s) => (
            <button
              key={s}
              onClick={() => onSuggestion?.(s)}
              className="whitespace-nowrap text-[11px] font-medium bg-white border border-indigo-200 text-indigo-700 px-2.5 py-1 rounded-full hover:bg-indigo-50 hover:border-indigo-300 active:scale-95 transition-all duration-150"
            >
              {s}
            </button>
          ))}
        </motion.div>
      )}
    </motion.div>
  );
}
