import SeverityBadge from "./SeverityBadge";

export interface MriResult {
  mime: string;
  body_region: string;
  sequence_guess: string;
  plane: string;
  anatomy_visible: string[];
  findings: string[];
  impressions: string[];
  severity: string;
  recommended_followup: string;
  limitations: string;
}

export default function MriViewer({
  imageUrl,
  result,
}: {
  imageUrl: string;
  result: MriResult;
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="glass p-3">
        <div className="text-xs uppercase tracking-wider text-muted mb-2">Image</div>
        <img
          src={imageUrl}
          alt="uploaded mri slice"
          className="w-full rounded-lg border border-border/60 bg-black"
        />
        <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
          <Tag label="Region" value={result.body_region} />
          <Tag label="Sequence" value={result.sequence_guess} />
          <Tag label="Plane" value={result.plane} />
        </div>
      </div>

      <div className="glass p-4 space-y-3">
        <SeverityBadge severity={result.severity} />
        <Section title="Anatomy visible" items={result.anatomy_visible} />
        <Section title="Findings" items={result.findings} />
        <Section title="Impressions" items={result.impressions} />
        {result.recommended_followup && (
          <div>
            <div className="text-xs uppercase tracking-wider text-muted">
              Recommended follow-up
            </div>
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

function Tag({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/70 bg-white/60 px-2 py-1">
      <div className="uppercase tracking-wider text-muted">{label}</div>
      <div className="text-text font-medium truncate" title={value}>
        {value.replace(/_/g, " ")}
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
