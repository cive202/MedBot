import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Send, ListChecks } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import ChatThread, { type Turn } from "@/components/ChatThread";
import ConversationSidebar from "@/components/ConversationSidebar";
import SocratesIntake from "@/components/SocratesIntake";
import FallbackSuggestions, { type FallbackEntry } from "@/components/FallbackSuggestions";
import { getConversation, streamChat, type ChatMeta, type ChatTurn } from "@/lib/chat";
import { useAuth } from "@/lib/auth";

/** Guests replay at most this many prior turns; the backend caps it too. */
const GUEST_HISTORY_LIMIT = 20;

/**
 * Chat works signed in or out.
 *
 * Signed in, conversations persist and the sidebar lists them. As a guest,
 * nothing is stored server-side, so the thread lives in component state and is
 * replayed to the backend with each request — which also means it disappears
 * on refresh. The sidebar is hidden in that mode since there is nothing to list.
 */
export default function Chat() {
  const { status } = useAuth();
  const authed = status === "authenticated";
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [intakeOpen, setIntakeOpen] = useState(false);
  const [loadingConv, setLoadingConv] = useState(false);
  // The assistant can be down while the rest of the app is fine: Ollama
  // stopped, the model still pulling, or the request failing outright. In
  // that state we offer pre-captured answers instead of a dead end.
  const [degraded, setDegraded] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    let cancelled = false;
    fetch("/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => {
        if (cancelled || !h) return;
        const m = h.medgemma ?? {};
        if (!m.ollama_running || !m.model_ready) setDegraded(true);
      })
      .catch(() => {
        if (!cancelled) setDegraded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  /** Answer from the frozen bundle: no network, nothing persisted. */
  function answerOffline(entry: FallbackEntry) {
    if (streaming) return;
    setError(null);
    setTurns((t) => [
      ...t,
      { id: crypto.randomUUID(), role: "user", content: entry.question },
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: entry.answer,
        offline: true,
      },
    ]);
  }

  async function loadConversation(id: string) {
    if (id === conversationId || streaming) return;
    setError(null);
    setLoadingConv(true);
    try {
      const conv = await getConversation(id);
      const restored: Turn[] = conv.messages.map((m) => ({
        id: m.id,
        role: m.role === "assistant" ? "assistant" : "user",
        content: m.content,
        meta: (m.extra ?? undefined) as Turn["meta"],
      }));
      setTurns(restored);
      setConversationId(conv.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoadingConv(false);
    }
  }

  function newConversation() {
    if (streaming) return;
    setTurns([]);
    setConversationId(null);
    setError(null);
    setDraft("");
  }

  async function send(messageArg?: string) {
    const message = (messageArg ?? draft).trim();
    if (!message || streaming) return;
    setError(null);
    if (!messageArg) setDraft("");

    const userTurn: Turn = { id: crypto.randomUUID(), role: "user", content: message };
    const assistantId = crypto.randomUUID();
    const assistantStub: Turn = { id: assistantId, role: "assistant", content: "", streaming: true };
    setTurns((t) => [...t, userTurn, assistantStub]);
    setStreaming(true);

    const isNew = conversationId === null;

    // `turns` still holds the pre-send thread here (the update above is
    // functional), which is exactly the history the backend needs from a guest.
    const guestHistory: ChatTurn[] | undefined = authed
      ? undefined
      : turns
          .filter((t) => t.content.trim())
          .map((t) => ({ role: t.role, content: t.content }))
          .slice(-GUEST_HISTORY_LIMIT);

    try {
      await streamChat(
        message,
        conversationId,
        {
          onMeta: (meta: ChatMeta) => {
            setConversationId(meta.conversation_id);
            setTurns((prev) => prev.map((t) => (t.id === assistantId ? { ...t, meta } : t)));
          },
          onDelta: (text) => {
            setTurns((prev) =>
              prev.map((t) => (t.id === assistantId ? { ...t, content: t.content + text } : t)),
            );
          },
          onError: (msg) => {
            setError(msg);
            setDegraded(true);
          },
          onDone: () => {
            setTurns((prev) =>
              prev.map((t) => (t.id === assistantId ? { ...t, streaming: false } : t)),
            );
          },
        },
        { history: guestHistory },
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setDegraded(true);
    } finally {
      setStreaming(false);
      setTurns((prev) =>
        prev.map((t) => (t.id === assistantId ? { ...t, streaming: false } : t)),
      );
      // Refresh the history sidebar so the new/updated thread appears.
      // Guests have no stored conversations, so there is nothing to refresh.
      if (authed) {
        const fn = isNew ? queryClient.refetchQueries : queryClient.invalidateQueries;
        void fn.call(queryClient, { queryKey: ["conversations"] });
      }
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  return (
    <div className="h-[calc(100vh-6.5rem)] flex">
      {authed && (
        <ConversationSidebar
          activeId={conversationId}
          onSelect={loadConversation}
          onNew={newConversation}
        />
      )}

      <section className="flex-1 flex min-w-0 px-2 sm:px-4 py-4">
        <div className="glass flex-1 flex flex-col overflow-hidden">
          <div className="px-5 pt-4 pb-3 border-b border-border/60 flex items-center justify-between gap-4">
            <div className="font-semibold">MedAssist</div>
            <div className="text-xs text-muted opacity-70 shrink-0">
              {authed
                ? conversationId
                  ? `chat ${conversationId.slice(0, 6)}`
                  : "new chat"
                : "guest — not saved"}
            </div>
          </div>

          {!authed && (
            <div className="mx-4 mt-3 text-sm rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-muted">
                You're chatting as a guest — this conversation won't be saved.
              </span>
              <Link to="/register" className="text-primary font-medium hover:underline">
                Create an account
              </Link>
              <span className="text-muted">to keep your history and health profile.</span>
            </div>
          )}

          {loadingConv ? (
            <div className="flex-1 grid place-items-center text-muted text-sm">
              Loading conversation…
            </div>
          ) : (
            <ChatThread turns={turns} />
          )}

          {error && (
            <div className="mx-4 mb-2 text-sm text-red-700 border border-red-300 bg-red-50 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          {degraded && <FallbackSuggestions onPick={answerOffline} disabled={streaming} />}

          <div className="border-t border-border/60 p-3 space-y-2">
            <div className="flex items-end gap-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={onKey}
                placeholder="Describe what you're experiencing in natural language — or start a guided SOCRATES check below."
                className="flex-1 min-h-[44px] max-h-40 resize-none"
                disabled={streaming || loadingConv}
              />
              <button
                onClick={() => void send()}
                disabled={streaming || loadingConv || !draft.trim()}
                className="btn-primary disabled:opacity-50"
              >
                <Send className="w-4 h-4" />
                <span className="hidden sm:inline">{streaming ? "Thinking…" : "Send"}</span>
              </button>
            </div>
            <button
              onClick={() => setIntakeOpen(true)}
              disabled={streaming || loadingConv}
              className="btn-ghost w-full justify-center disabled:opacity-50"
            >
              <ListChecks className="w-4 h-4" />
              Guided symptom check for Pain analysis (SOCRATES)
            </button>
          </div>
        </div>
      </section>

      {intakeOpen && (
        <SocratesIntake
          onCancel={() => setIntakeOpen(false)}
          onComplete={(composed) => {
            setIntakeOpen(false);
            void send(composed);
          }}
        />
      )}
    </div>
  );
}
