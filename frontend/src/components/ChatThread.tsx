import { useEffect, useRef } from "react";
import type { ChatMeta } from "@/lib/chat";
import SeverityBadge from "./SeverityBadge";
import SpecialistCard from "./SpecialistCard";

export interface Turn {
  id: string;
  role: "user" | "assistant";
  content: string;
  meta?: ChatMeta;
  streaming?: boolean;
}

export default function ChatThread({ turns }: { turns: Turn[] }) {
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  return (
    <div className="flex-1 overflow-y-auto px-2 py-4 space-y-4">
      {turns.length === 0 && (
        <div className="text-center text-muted text-sm py-12">
          Describe your symptoms in plain language. The assistant uses a Random Forest classifier and
          retrieval-augmented MedGemma to suggest possibilities.
        </div>
      )}
      {turns.map((t) => (
        <Bubble key={t.id} turn={t} />
      ))}
      <div ref={bottom} />
    </div>
  );
}

function Bubble({ turn }: { turn: Turn }) {
  const isUser = turn.role === "user";
  return (
    <div className={"flex " + (isUser ? "justify-end" : "justify-start")}>
      <div
        className={
          "max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed " +
          (isUser ? "bg-primary/10 border border-primary/40 text-text" : "glass")
        }
      >
        {!isUser && turn.meta && <MetaBlock meta={turn.meta} />}
        {turn.content}
        {turn.streaming && (
          <span className="inline-block w-2 h-4 ml-1 align-middle bg-primary animate-pulse rounded-sm" />
        )}
        {!isUser && turn.meta?.nearby_specialists && turn.meta.nearby_specialists.length > 0 && (
          <div className="mt-4 space-y-2">
            <div className="text-xs uppercase tracking-wider text-muted">Nearby specialists</div>
            {turn.meta.nearby_specialists.slice(0, 5).map((s, i) => (
              <SpecialistCard
                key={`${s.Doctor_ID ?? i}-${s.Latitude},${s.Longitude}`}
                s={s}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MetaBlock({ meta }: { meta: ChatMeta }) {
  const hasAnything =
    meta.symptoms.length > 0 || meta.candidates.length > 0 || meta.severity;
  if (!hasAnything) return null;
  return (
    <div className="mb-3 text-xs space-y-2">
      {meta.severity && (
        <SeverityBadge
          severity={meta.severity}
          specialty={meta.specialty}
          reasoning={meta.severity_reasoning}
        />
      )}
      {meta.symptoms.length > 0 && (
        <div>
          <span className="text-muted">Symptoms detected: </span>
          {meta.symptoms.map((s) => (
            <span
              key={s}
              className="inline-block mr-1 mb-1 px-2 py-0.5 rounded-full bg-surface/80 border border-border/70"
            >
              {s}
            </span>
          ))}
        </div>
      )}
      {meta.candidates.length > 0 && (
        <div>
          <span className="text-muted">RF candidates: </span>
          {meta.candidates.map((c) => (
            <span
              key={c.disease}
              className="inline-block mr-1 mb-1 px-2 py-0.5 rounded-full bg-accent/15 border border-accent/30"
            >
              {c.disease} {(c.probability * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
