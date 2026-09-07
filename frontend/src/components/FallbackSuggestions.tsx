import { WifiOff } from "lucide-react";
import entries from "@/data/fallbackAnswers.json";

export interface FallbackEntry {
  question: string;
  answer: string;
  severity?: string | null;
  specialty?: string | null;
  retrieved?: string[];
}

/**
 * Answers captured from the live model and frozen into the bundle, so the app
 * still has something useful to say when MedGemma is unreachable.
 */
export const FALLBACK_ENTRIES = entries as FallbackEntry[];

export default function FallbackSuggestions({
  onPick,
  disabled = false,
}: {
  onPick: (entry: FallbackEntry) => void;
  disabled?: boolean;
}) {
  if (FALLBACK_ENTRIES.length === 0) return null;

  return (
    <div className="mx-4 mb-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-3">
      <div className="flex items-center gap-2 text-sm font-medium text-amber-900">
        <WifiOff className="w-4 h-4 shrink-0" />
        The AI assistant is unavailable right now
      </div>
      <p className="mt-1 text-xs text-amber-800">
        Below are saved answers to common questions, captured earlier from this same
        assistant. They are general information — not a response to your situation.
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {FALLBACK_ENTRIES.map((e) => (
          <button
            key={e.question}
            type="button"
            onClick={() => onPick(e)}
            disabled={disabled}
            className="text-left text-xs rounded-full border border-amber-400/70 bg-white/70 px-3 py-1.5 hover:bg-white disabled:opacity-50"
          >
            {e.question}
          </button>
        ))}
      </div>
    </div>
  );
}
