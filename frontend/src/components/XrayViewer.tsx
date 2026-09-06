import SeverityBadge from "./SeverityBadge";

export interface XrayResult {
  mime: string;
  modality_guess: string;
  findings: string[];
  impressions: string[];
  severity: string;
  recommended_followup: string;
  limitations: string;
}

export default function XrayViewer({ imageUrl, result }: { imageUrl: string; result: XrayResult }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="glass p-3">
        <div className="text-xs uppercase tracking-wider text-muted mb-2">Image</div>
        <img src={imageUrl} alt="uploaded x-ray" className="w-full rounded-lg border border-border/60" />
        <div className="text-xs text-muted mt-2">
          Modality guess: <span className="text-text">{result.modality_guess.replace(/_/g, " ")}</span>
        </div>
      </div>

      <div className="glass p-4 space-y-3">
        <SeverityBadge severity={result.severity} />
        <Section title="Findings" items={result.findings} />
        <Section title="Impressions" items={result.impressions} />
        {result.recommended_followup && (
          <div>
            <div className="text-xs uppercase tracking-wider text-muted">Recommended follow-up</div>
            <div className="text-sm">{result.recommended_followup}</div>
          </div>
        )}
        {result.limitations && (
          <div className="text-xs text-muted border-t border-border/40 pt-2">
            <span className="font-semibold">Limitations:</span> {result.limitations}
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, items }: { title: string; items: string[] }) {
  if (!items?.length) return null;
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted">{title}</div>
      <ul className="list-disc pl-5 text-sm space-y-1">
        {items.map((s, i) => (
          <li key={i}>{s}</li>
        ))}
      </ul>
    </div>
  );
}
