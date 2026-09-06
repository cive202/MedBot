import { useQuery } from "@tanstack/react-query";
import { MessageSquarePlus, MessageCircle } from "lucide-react";
import { listConversations, type ConversationSummary } from "@/lib/chat";

interface Props {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

export default function ConversationSidebar({ activeId, onSelect, onNew }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
    refetchInterval: 15000,
  });

  return (
    <aside className="hidden md:flex md:w-72 shrink-0 flex-col border-r border-border/60 bg-white/60 backdrop-blur-sm">
      <div className="p-3 border-b border-border/60">
        <button
          onClick={onNew}
          className="btn-primary w-full justify-start"
          aria-label="Start a new conversation"
        >
          <MessageSquarePlus className="w-4 h-4" />
          New conversation
        </button>
      </div>

      <div className="text-[11px] uppercase tracking-wider text-muted px-4 pt-3 pb-1">
        History
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {isLoading && <div className="text-muted text-sm px-2 py-4">Loading…</div>}
        {isError && (
          <div className="text-red-700 text-sm px-2 py-4">Couldn't load history.</div>
        )}
        {data && data.length === 0 && (
          <div className="text-muted text-sm px-2 py-4">
            No conversations yet. Start one on the right →
          </div>
        )}
        {data?.map((c) => (
          <ConversationItem
            key={c.id}
            conv={c}
            active={c.id === activeId}
            onClick={() => onSelect(c.id)}
          />
        ))}
      </div>
    </aside>
  );
}

function ConversationItem({
  conv,
  active,
  onClick,
}: {
  conv: ConversationSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "w-full text-left rounded-xl px-3 py-2 mb-1 text-sm transition flex items-start gap-2 " +
        (active
          ? "bg-primary/15 border border-primary/40"
          : "hover:bg-surface/80 border border-transparent")
      }
    >
      <MessageCircle className={"w-4 h-4 mt-0.5 shrink-0 " + (active ? "text-primary" : "text-muted")} />
      <div className="min-w-0 flex-1">
        <div className="truncate">{conv.title || "Conversation"}</div>
        <div className="text-[11px] text-muted">{formatWhen(conv.updated_at)}</div>
      </div>
    </button>
  );
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMin = Math.round((now.getTime() - d.getTime()) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffMin < 60 * 24) return `${Math.round(diffMin / 60)}h ago`;
  return d.toLocaleDateString();
}
