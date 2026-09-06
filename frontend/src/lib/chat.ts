/**
 * Streams a chat response from the backend via Server-Sent Events over fetch().
 *
 * EventSource can't POST with cookies, so we read the SSE wire format directly
 * from a fetch() ReadableStream.
 */
import { api } from "./api";
import type { Specialist } from "@/components/SpecialistCard";

export interface ChatMeta {
  /** Null for guests — nothing was persisted, so there is nothing to resume. */
  conversation_id: string | null;
  symptoms: string[];
  candidates: { disease: string; probability: number }[];
  retrieved: { disease: string; section: string }[];
  severity?: string;
  specialty?: string;
  severity_reasoning?: string;
  nearby_specialists?: Specialist[];
}

export interface ChatStreamCallbacks {
  onMeta: (meta: ChatMeta) => void;
  onDelta: (text: string) => void;
  onError: (msg: string) => void;
  onDone: () => void;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

export interface StoredMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  extra: Record<string, unknown> | null;
  created_at: string;
}

export interface ConversationDetail {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: StoredMessage[];
}

export async function listConversations(): Promise<ConversationSummary[]> {
  const r = await api.get<ConversationSummary[]>("/api/conversations");
  return r.data;
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const r = await api.get<ConversationDetail>(`/api/conversations/${id}`);
  return r.data;
}

export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

export interface StreamChatOptions {
  /**
   * Prior turns to replay. Guests have no server-side history, so the client
   * sends its own. Ignored by the backend for signed-in callers, which read
   * history from the database instead.
   */
  history?: ChatTurn[];
  signal?: AbortSignal;
}

export async function streamChat(
  message: string,
  conversationId: string | null,
  cb: ChatStreamCallbacks,
  opts: StreamChatOptions = {},
): Promise<void> {
  const r = await fetch("/api/chat", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      history: opts.history ?? [],
    }),
    signal: opts.signal,
  });

  if (!r.ok || !r.body) {
    const txt = await r.text().catch(() => "");
    throw new Error(`Chat request failed (${r.status}): ${txt || r.statusText}`);
  }

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    let idx: number;
    while ((idx = buf.indexOf("\n\n")) !== -1) {
      const raw = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const { event, data } = parseSseFrame(raw);
      if (!data) continue;
      try {
        const parsed = JSON.parse(data);
        if (event === "meta") cb.onMeta(parsed as ChatMeta);
        else if (event === "delta") cb.onDelta(parsed.text as string);
        else if (event === "error") cb.onError(parsed.message as string);
        else if (event === "done") cb.onDone();
      } catch {
        /* ignore */
      }
    }
  }
}

function parseSseFrame(raw: string): { event: string; data: string } {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  return { event, data: dataLines.join("\n") };
}
