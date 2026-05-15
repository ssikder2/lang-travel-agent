"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "framer-motion";
import Message, { MessageData, ToolUsed } from "./Message";
import TypingIndicator from "./TypingIndicator";
import ChatInput from "./ChatInput";
import { streamChat, resetSession } from "@/lib/api";
import type { CardsData, TripProfileSnapshot } from "@/lib/types";

const STARTER_SUGGESTIONS = ["Tokyo 🇯🇵", "Paris 🇫🇷", "Bali 🌴", "Southeast Asia trip", "Surprise me"];

const WELCOME_MESSAGE: Omit<MessageData, "timestamp"> = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi there! I'm Wayfarer, your AI travel assistant. ✈️\n\nI can help with flights, hotels, itineraries, budgets, packing lists, visa requirements, and more.\n\nA quick way to get started is filling out the Trip Snapshot on the left. It's totally optional — if you're not sure yet, just chat with me and I'll help you figure it out step by step.",
  suggestions: STARTER_SUGGESTIONS,
};

const EPOCH = new Date(0);

export default function ChatWindow({
  onClose,
  onCards,
  onProfile,
  onSessionReset,
  onSessionId,
}: {
  onClose?: () => void;
  onCards?: (data: CardsData | null) => void;
  onProfile?: (profile: TripProfileSnapshot) => void;
  onSessionReset?: () => void;
  onSessionId?: (id: string) => void;
}) {
  const [messages, setMessages] = useState<MessageData[]>([
    { ...WELCOME_MESSAGE, timestamp: EPOCH },
  ]);
  const [isTyping, setIsTyping] = useState(false);
  const [activeSuggestionId, setActiveSuggestionId] = useState<string>("welcome");
  const [inputPlaceholder, setInputPlaceholder] = useState<string | undefined>(undefined);
  const bottomRef = useRef<HTMLDivElement>(null);

  const sessionId = useRef<string>("");
  useEffect(() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem("wayfarer_session_id", id);
    sessionId.current = id;
    onSessionId?.(id);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isSendingRef = useRef(false);
  const isResettingRef = useRef(false);

  useEffect(() => {
    setMessages((prev) =>
      prev.map((m) => (m.id === "welcome" ? { ...m, timestamp: new Date() } : m)),
    );
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const handleSend = useCallback(
    async (text: string) => {
      if (isSendingRef.current) return;
      isSendingRef.current = true;

      setActiveSuggestionId("");

      const userMessage: MessageData = {
        id: crypto.randomUUID(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsTyping(true);

      const toolMessageIds: string[] = [];
      const turnTools: ToolUsed[] = [];
      const turnMemoryFields: Set<string> = new Set();
      const assistantId = crypto.randomUUID();

      try {
        for await (const event of streamChat(text, sessionId.current)) {
          if (event.type === "tool") {
            turnTools.push({ tool: event.tool, label: event.label });
            const toolMsg: MessageData = {
              id: crypto.randomUUID(),
              role: "tool",
              content: event.tool,
              label: event.label,
              timestamp: new Date(),
            };
            toolMessageIds.push(toolMsg.id);
            setMessages((prev) => [...prev, toolMsg]);
          } else if (event.type === "memory") {
            event.fields.forEach((f) => turnMemoryFields.add(f));
          } else if (event.type === "profile") {
            onProfile?.(event.profile);
          } else if (event.type === "cards") {
            onCards?.({ kind: event.kind, label: event.label, cards: event.cards } as CardsData);
          } else if (event.type === "done") {
            const memoryFieldsArr = Array.from(turnMemoryFields);
            const replyBody = event.reply ?? "";
            setMessages((prev) => {
              const withoutTools = prev.filter((m) => !toolMessageIds.includes(m.id));
              const idx = withoutTools.findIndex((m) => m.id === assistantId);
              const merged = {
                id: assistantId,
                role: "assistant" as const,
                content: replyBody,
                suggestions: event.suggestions,
                toolsUsed: turnTools.length > 0 ? [...turnTools] : undefined,
                memorySaved: memoryFieldsArr.length > 0 ? memoryFieldsArr : undefined,
                timestamp: new Date(),
              };
              if (idx >= 0) {
                return withoutTools.map((m) =>
                  m.id === assistantId ? { ...m, ...merged } : m,
                );
              }
              return [...withoutTools, merged];
            });
            setActiveSuggestionId(assistantId);
            if (event.placeholder) setInputPlaceholder(event.placeholder);
            setIsTyping(false);
          } else if (event.type === "error") {
            setMessages((prev) => [
              ...prev.filter((m) => !toolMessageIds.includes(m.id)),
              {
                id: crypto.randomUUID(),
                role: "assistant",
                content: `Sorry, something went wrong: ${event.message}`,
                timestamp: new Date(),
              },
            ]);
            setIsTyping(false);
          }
        }
      } catch {
        setMessages((prev) => [
          ...prev.filter((m) => !toolMessageIds.includes(m.id)),
          {
            id: crypto.randomUUID(),
            role: "assistant",
            content: "Sorry, I lost connection to the server. Please try again.",
            timestamp: new Date(),
          },
        ]);
        setIsTyping(false);
      } finally {
        isSendingRef.current = false;
      }
    },
    [onCards, onProfile],
  );

  const handleReset = useCallback(async () => {
    if (isResettingRef.current) return;
    isResettingRef.current = true;
    try {
      await resetSession(sessionId.current);
      const newId = crypto.randomUUID();
      sessionStorage.setItem("wayfarer_session_id", newId);
      sessionId.current = newId;
      onSessionId?.(newId);
      setMessages([{ ...WELCOME_MESSAGE, timestamp: new Date() }]);
      setActiveSuggestionId("welcome");
      onCards?.(null);
      onSessionReset?.();
    } finally {
      isResettingRef.current = false;
    }
  }, [onCards, onSessionReset]);

  return (
    <div className="flex flex-col h-full bg-white">
      {/* ── Header ────────────────────────────────────────────── */}
      <header className="flex-shrink-0 h-14 flex items-center justify-between px-4 bg-white border-b border-black/[0.05]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-brand shrink-0">
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
          <div>
            <p className="text-sm font-bold text-stone-800 leading-none">Wayfarer</p>
            <div className="flex items-center gap-1 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <p className="text-[10px] text-stone-400">AI Travel Assistant</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Reset button */}
          <button
            onClick={handleReset}
            title="Start a new trip"
            aria-label="Start a new trip"
            className="w-8 h-8 rounded-xl border border-black/[0.07] bg-stone-50 flex items-center justify-center text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition-colors"
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
              <path d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
          </button>

          {/* Close button */}
          {onClose && (
            <button
              onClick={onClose}
              title="Close chat"
              aria-label="Close chat panel"
              className="w-8 h-8 rounded-xl border border-black/[0.07] bg-stone-50 flex items-center justify-center text-stone-400 hover:bg-stone-100 hover:text-stone-600 transition-colors"
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
                <path d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
              </svg>
            </button>
          )}
        </div>
      </header>

      {/* ── Message list ─────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto scrollbar-thin px-4 py-4 space-y-3">
        {messages.map((msg) => (
          <Message
            key={msg.id}
            message={msg}
            showSuggestions={msg.id === activeSuggestionId}
            onSuggestion={handleSend}
          />
        ))}

        <AnimatePresence>
          {isTyping && (
            <motion.div
              key="typing"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 8 }}
              transition={{ duration: 0.2 }}
            >
              <TypingIndicator />
            </motion.div>
          )}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>

      {/* ── Input ────────────────────────────────────────────── */}
      <div className="flex-shrink-0 border-t border-black/[0.05]">
        <ChatInput
          onSend={handleSend}
          disabled={isTyping}
          placeholder={inputPlaceholder}
        />
      </div>
    </div>
  );
}
