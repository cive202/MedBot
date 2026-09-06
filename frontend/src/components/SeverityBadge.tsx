type Severity = "low" | "moderate" | "critical";

const STYLES: Record<Severity, string> = {
  low: "bg-emerald-50 text-emerald-800 border-emerald-400",
  moderate: "bg-amber-50 text-amber-800 border-amber-400",
  critical: "bg-red-50 text-red-800 border-red-500 animate-pulse",
};

const LABELS: Record<Severity, string> = {
  low: "Low — minor, self-care usually fine",
  moderate: "Moderate — potentially harmful, see a clinician soon",
  critical: "Critical — fatal risk, consult a professional immediately",
};

/**
 * Map any incoming severity string (including legacy values like "mild" or
 * "severe" from older stored conversations) onto the current 3-level scheme.
 */
function normalize(raw: string): Severity {
  const s = (raw || "").toLowerCase().trim();
  if (s === "low" || s === "moderate" || s === "critical") return s as Severity;
  if (s === "mild") return "low";
  if (s === "severe" || s === "emergency") return "critical";
  return "moderate";
}

export default function SeverityBadge({
  severity,
  specialty,
  reasoning,
}: {
  severity: string;
  specialty?: string;
  reasoning?: string;
}) {
  const s = normalize(severity);
  return (
    <div className={"inline-flex flex-col gap-1 rounded-xl border px-3 py-2 text-xs " + STYLES[s]}>
      <div className="flex items-center gap-2">
        <span className="font-semibold uppercase tracking-wider">{LABELS[s]}</span>
        {specialty && <span className="opacity-80">· {specialty.replace(/_/g, " ")}</span>}
      </div>
      {reasoning && <span className="opacity-80">{reasoning}</span>}
    </div>
  );
}
