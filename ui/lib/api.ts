import type { CardsData, TripProfileSnapshot } from "./types";

export type SSEEvent =
  | { type: "token"; delta: string }
  | { type: "tool"; tool: string; label: string }
  | { type: "memory"; fields: string[] }
  | { type: "profile"; profile: TripProfileSnapshot }
  | { type: "cards" } & CardsData
  | {
      type: "done";
      reply: string;
      suggestions?: string[];
      placeholder?: string;
    }
  | { type: "error"; message: string };

/**
 * Streams chat events from the Python backend via SSE.
 * Yields SSEEvent objects as they arrive.
 */
export async function* streamChat(
  message: string,
  sessionId: string
): AsyncGenerator<SSEEvent> {
  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

  let response: Response;
  try {
    response = await fetch(`${backendUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
  } catch {
    yield { type: "error", message: "Could not reach the backend. Make sure the server is running." };
    return;
  }

  if (!response.ok) {
    yield { type: "error", message: `Backend returned ${response.status}: ${response.statusText}` };
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    yield { type: "error", message: "Readable stream not available." };
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Keep the last (potentially incomplete) line in the buffer
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          yield JSON.parse(raw) as SSEEvent;
        } catch {
          // Malformed SSE line — skip
        }
      }
    }
  } finally {
    reader.cancel();
  }
}

export async function resetSession(sessionId: string): Promise<void> {
  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  await fetch(`${backendUrl}/api/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export interface SnapshotFields {
  destinations?: string;
  travel_dates?: string;
  num_travelers?: number;
  travel_style?: string;
  flight_departure?: string;
  flight_outbound_ymd?: string;
  flight_return_ymd?: string;
  budget_estimate?: string;
}

export async function syncProfile(
  sessionId: string,
  fields: SnapshotFields,
): Promise<void> {
  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
  try {
    await fetch(`${backendUrl}/api/sync-profile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, ...fields }),
    });
  } catch {
    // Best-effort — don't block the UI if the sync fails
  }
}
