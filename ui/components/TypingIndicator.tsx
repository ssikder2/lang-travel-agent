"use client";

export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-2">
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-[10px] font-bold text-white">
        W
      </div>
      <div className="bg-stone-100 border border-black/[0.04] rounded-2xl rounded-bl-sm px-3.5 py-2.5">
        <div className="flex items-center gap-1.5 h-4">
          <span className="bounce-dot w-1.5 h-1.5 rounded-full bg-stone-400 inline-block" />
          <span className="bounce-dot w-1.5 h-1.5 rounded-full bg-stone-400 inline-block" />
          <span className="bounce-dot w-1.5 h-1.5 rounded-full bg-stone-400 inline-block" />
        </div>
      </div>
    </div>
  );
}
