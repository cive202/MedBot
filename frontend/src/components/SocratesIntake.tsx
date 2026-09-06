import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, Send, X } from "lucide-react";

/**
 * Fixed SOCRATES symptom intake (no backend round-trip per step).
 *
 *   S  Site                       — Where is it?
 *   O  Onset                      — When did it start? Sudden/gradual?
 *   C  Character                  — Sharp, dull, burning, ...?
 *   R  Radiation                  — Does it spread?
 *   A  Associations               — Other symptoms with it?
 *   T  Time course                — Constant / intermittent / pattern?
 *   E  Exacerbating / Relieving   — What makes it worse / better?
 *   S  Severity                   — 1-10
 *
 * Each step renders a step-appropriate input. On completion we compose a
 * structured markdown message ready to drop into the chat thread — Chat.tsx
 * already calls `send(composed)` on `onComplete`.
 */

interface IntakeAnswer {
  key: string;
  question: string;
  answer: string;
  letter: string;
  letter_label: string;
}

interface Props {
  onCancel: () => void;
  onComplete: (composedMessage: string, answers: IntakeAnswer[]) => void;
}

interface StepDef {
  key: string;
  letter: string;
  letter_label: string;
  question: string;
  hint?: string;
  required?: boolean;
}

const STEPS: StepDef[] = [
  {
    key: "site",
    letter: "S",
    letter_label: "Site",
    question: "Where is the pain or symptom located?",
    hint: "e.g. lower right abdomen, behind the eyes, left side of the chest",
    required: true,
  },
  {
    key: "onset",
    letter: "O",
    letter_label: "Onset",
    question: "When did it start, and was it sudden or gradual?",
    hint: "e.g. 'yesterday morning, gradual' or '20 minutes ago, sudden'",
    required: true,
  },
  {
    key: "character",
    letter: "C",
    letter_label: "Character",
    question: "What does it feel like?",
    hint: "Pick any that fit, and add your own words if helpful.",
    required: true,
  },
  {
    key: "radiation",
    letter: "R",
    letter_label: "Radiation",
    question: "Does it spread anywhere else?",
    hint: "e.g. from chest into the left arm, or stays in one spot",
  },
  {
    key: "associations",
    letter: "A",
    letter_label: "Associations",
    question: "Any other symptoms happening alongside it?",
    hint: "Tick any common ones and add anything else.",
  },
  {
    key: "time_course",
    letter: "T",
    letter_label: "Time course",
    question: "Is it constant or does it come and go? Any pattern?",
    hint: "e.g. constant since onset; comes in waves every 30 min; worse at night",
  },
  {
    key: "exacerbating_relieving",
    letter: "E",
    letter_label: "Exacerbating & relieving factors",
    question: "What makes it worse, and what makes it better?",
    hint: "e.g. worse when bending forward; better with rest and ibuprofen",
  },
  {
    key: "severity",
    letter: "S",
    letter_label: "Severity",
    question: "How bad is it right now?",
    hint: "0 = no symptoms, 10 = worst imaginable.",
    required: true,
  },
];

const CHARACTER_CHIPS = [
  "sharp", "dull", "burning", "throbbing", "aching",
  "cramping", "stabbing", "pressure", "tingling", "itching",
  "tightness", "shooting",
];

const ASSOCIATION_CHIPS = [
  "fever", "chills", "nausea", "vomiting", "diarrhoea", "constipation",
  "headache", "dizziness", "shortness of breath", "sweating",
  "fatigue", "loss of appetite", "rash", "cough", "sore throat",
];

const BODY_REGION_CHIPS = [
  "head", "eye", "ear", "throat", "neck", "chest", "back",
  "abdomen", "pelvis", "arm", "leg", "joint", "skin",
];

export default function SocratesIntake({ onCancel, onComplete }: Props) {
  const [stepIdx, setStepIdx] = useState(0);
  const [siteRegion, setSiteRegion] = useState<string[]>([]);
  const [site, setSite] = useState("");
  const [onsetWhen, setOnsetWhen] = useState("");
  const [onsetMode, setOnsetMode] = useState<"sudden" | "gradual" | "">("");
  const [characterChips, setCharacterChips] = useState<string[]>([]);
  const [characterOther, setCharacterOther] = useState("");
  const [radiationYes, setRadiationYes] = useState<"yes" | "no" | "">("");
  const [radiationWhere, setRadiationWhere] = useState("");
  const [associationChips, setAssociationChips] = useState<string[]>([]);
  const [associationOther, setAssociationOther] = useState("");
  const [timePattern, setTimePattern] = useState<"constant" | "intermittent" | "">("");
  const [timeNote, setTimeNote] = useState("");
  const [worse, setWorse] = useState("");
  const [better, setBetter] = useState("");
  const [severity, setSeverity] = useState<number>(5);

  const focusable = useRef<HTMLElement | null>(null);
  useEffect(() => {
    focusable.current?.focus();
  }, [stepIdx]);

  const def = STEPS[stepIdx];
  const isLast = stepIdx === STEPS.length - 1;

  const answerForStep = (key: string): string => {
    switch (key) {
      case "site":
        return joinNonEmpty([combineChips(siteRegion), site.trim()], "; ");
      case "onset":
        return joinNonEmpty([onsetWhen.trim(), onsetMode], ", ");
      case "character":
        return joinNonEmpty([combineChips(characterChips), characterOther.trim()], "; ");
      case "radiation":
        if (!radiationYes) return "";
        if (radiationYes === "no") return "does not spread";
        return joinNonEmpty(["spreads", radiationWhere.trim()], ": ");
      case "associations":
        return joinNonEmpty(
          [combineChips(associationChips), associationOther.trim()],
          "; ",
        );
      case "time_course":
        return joinNonEmpty([timePattern, timeNote.trim()], ", ");
      case "exacerbating_relieving": {
        const w = worse.trim() ? `worse with ${worse.trim()}` : "";
        const b = better.trim() ? `better with ${better.trim()}` : "";
        return joinNonEmpty([w, b], "; ");
      }
      case "severity":
        return `${severity}/10`;
      default:
        return "";
    }
  };

  const canAdvance = useMemo(() => {
    if (def.required) return Boolean(answerForStep(def.key));
    return true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    def, site, siteRegion, onsetWhen, onsetMode,
    characterChips, characterOther,
    radiationYes, radiationWhere,
    associationChips, associationOther,
    timePattern, timeNote,
    worse, better, severity,
  ]);

  const answeredSoFar: IntakeAnswer[] = STEPS.slice(0, stepIdx)
    .map((s) => ({
      key: s.key,
      letter: s.letter,
      letter_label: s.letter_label,
      question: s.question,
      answer: answerForStep(s.key) || "(skipped)",
    }));

  function next() {
    if (!canAdvance) return;
    if (isLast) {
      const allAnswers: IntakeAnswer[] = STEPS.map((s) => ({
        key: s.key,
        letter: s.letter,
        letter_label: s.letter_label,
        question: s.question,
        answer: answerForStep(s.key) || "(skipped)",
      }));
      const composed = composeMarkdown(allAnswers);
      onComplete(composed, allAnswers);
      return;
    }
    setStepIdx((i) => i + 1);
  }

  function back() {
    if (stepIdx === 0) {
      onCancel();
      return;
    }
    setStepIdx((i) => i - 1);
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="glass w-full max-w-2xl p-6 sm:p-8 relative max-h-[92vh] overflow-y-auto">
        <button
          onClick={onCancel}
          className="absolute top-3 right-3 p-1 rounded hover:bg-white/80"
          aria-label="Close"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-2 text-xs text-muted">
          <span className="font-semibold tracking-wider">SOCRATES INTAKE</span>
          <span className="opacity-50">·</span>
          <span>Step {stepIdx + 1} of {STEPS.length} — {def.letter_label}</span>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 rounded-full bg-white/60 overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300"
            style={{ width: `${((stepIdx + 1) / STEPS.length) * 100}%` }}
          />
        </div>

        {/* Letter rail */}
        <div className="mt-4 flex flex-wrap items-center gap-1.5 text-[11px] uppercase tracking-wider">
          {STEPS.map((s, i) => {
            const isCurrent = i === stepIdx;
            const isDone = i < stepIdx;
            return (
              <span
                key={s.key}
                className={
                  "px-2 py-0.5 rounded-full border " +
                  (isCurrent
                    ? "bg-primary text-white border-primary"
                    : isDone
                      ? "bg-primary/10 border-primary/40 text-primary"
                      : "border-border/70 text-muted")
                }
                title={s.letter_label}
              >
                {s.letter}
              </span>
            );
          })}
        </div>

        {/* Question */}
        <div className="mt-6 text-sm leading-snug">{def.question}</div>

        {/* Step body */}
        <div className="mt-4">
          <StepBody
            def={def}
            focusable={focusable}
            // controlled state
            siteRegion={siteRegion}
            setSiteRegion={setSiteRegion}
            site={site}
            setSite={setSite}
            onsetWhen={onsetWhen}
            setOnsetWhen={setOnsetWhen}
            onsetMode={onsetMode}
            setOnsetMode={setOnsetMode}
            characterChips={characterChips}
            setCharacterChips={setCharacterChips}
            characterOther={characterOther}
            setCharacterOther={setCharacterOther}
            radiationYes={radiationYes}
            setRadiationYes={setRadiationYes}
            radiationWhere={radiationWhere}
            setRadiationWhere={setRadiationWhere}
            associationChips={associationChips}
            setAssociationChips={setAssociationChips}
            associationOther={associationOther}
            setAssociationOther={setAssociationOther}
            timePattern={timePattern}
            setTimePattern={setTimePattern}
            timeNote={timeNote}
            setTimeNote={setTimeNote}
            worse={worse}
            setWorse={setWorse}
            better={better}
            setBetter={setBetter}
            severity={severity}
            setSeverity={setSeverity}
            onSubmit={next}
          />
        </div>

        {/* Live preview of what they've said so far */}
        {answeredSoFar.length > 0 && (
          <details className="mt-5 group">
            <summary className="text-xs text-muted cursor-pointer select-none">
              Review {answeredSoFar.length} previous answer{answeredSoFar.length === 1 ? "" : "s"}
            </summary>
            <ul className="mt-2 text-sm space-y-1">
              {answeredSoFar.map((a) => (
                <li key={a.key}>
                  <span className="font-semibold">{a.letter_label}:</span>{" "}
                  <span className="text-muted">{a.answer}</span>
                </li>
              ))}
            </ul>
          </details>
        )}

        {/* Nav */}
        <div className="mt-6 flex items-center justify-between gap-3">
          <button onClick={back} className="btn-ghost">
            <ArrowLeft className="w-4 h-4" />
            {stepIdx === 0 ? "Cancel" : "Back"}
          </button>
          <div className="flex items-center gap-2">
            {!def.required && (
              <button onClick={next} className="btn-ghost" title="Skip this question">
                Skip
              </button>
            )}
            <button
              onClick={next}
              className="btn-primary disabled:opacity-50"
              disabled={!canAdvance}
            >
              {isLast ? (
                <>
                  <Check className="w-4 h-4" />
                  Finish & send
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  Next
                </>
              )}
            </button>
          </div>
        </div>

        <div className="mt-4 text-[11px] text-muted opacity-70">
          Tip: press <kbd className="px-1 border border-border/70 rounded">Enter</kbd> in a text
          field to move on. {def.required ? "This step is required." : "This step is optional — feel free to skip."}
        </div>
      </div>
    </div>
  );
}

/* ----------------------- Step body ----------------------- */

interface StepBodyProps {
  def: StepDef;
  focusable: React.MutableRefObject<HTMLElement | null>;
  siteRegion: string[]; setSiteRegion: (v: string[]) => void;
  site: string; setSite: (v: string) => void;
  onsetWhen: string; setOnsetWhen: (v: string) => void;
  onsetMode: "sudden" | "gradual" | ""; setOnsetMode: (v: "sudden" | "gradual" | "") => void;
  characterChips: string[]; setCharacterChips: (v: string[]) => void;
  characterOther: string; setCharacterOther: (v: string) => void;
  radiationYes: "yes" | "no" | ""; setRadiationYes: (v: "yes" | "no" | "") => void;
  radiationWhere: string; setRadiationWhere: (v: string) => void;
  associationChips: string[]; setAssociationChips: (v: string[]) => void;
  associationOther: string; setAssociationOther: (v: string) => void;
  timePattern: "constant" | "intermittent" | ""; setTimePattern: (v: "constant" | "intermittent" | "") => void;
  timeNote: string; setTimeNote: (v: string) => void;
  worse: string; setWorse: (v: string) => void;
  better: string; setBetter: (v: string) => void;
  severity: number; setSeverity: (v: number) => void;
  onSubmit: () => void;
}

function StepBody(p: StepBodyProps) {
  const { def, focusable } = p;
  const onKey = (e: React.KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !(e.target as HTMLElement).tagName.match(/TEXTAREA/i)) {
      e.preventDefault();
      p.onSubmit();
    }
  };

  switch (def.key) {
    case "site":
      return (
        <div className="space-y-3">
          <div>
            <Label hint={def.hint}>Body region (optional)</Label>
            <ChipMultiSelect
              options={BODY_REGION_CHIPS}
              value={p.siteRegion}
              onChange={p.setSiteRegion}
            />
          </div>
          <div>
            <Label>Describe the location in your own words</Label>
            <input
              ref={(el) => (focusable.current = el)}
              className="w-full"
              placeholder="e.g. lower right abdomen, behind the right eye…"
              value={p.site}
              onChange={(e) => p.setSite(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
        </div>
      );

    case "onset":
      return (
        <div className="space-y-3">
          <div>
            <Label hint={def.hint}>When did it start?</Label>
            <input
              ref={(el) => (focusable.current = el)}
              className="w-full"
              placeholder="e.g. yesterday morning, 30 min ago, last Tuesday…"
              value={p.onsetWhen}
              onChange={(e) => p.setOnsetWhen(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
          <div>
            <Label>How did it start?</Label>
            <RadioRow
              options={[
                { value: "sudden", label: "Suddenly" },
                { value: "gradual", label: "Gradually" },
              ]}
              value={p.onsetMode}
              onChange={(v) => p.setOnsetMode(v as "sudden" | "gradual")}
            />
          </div>
        </div>
      );

    case "character":
      return (
        <div className="space-y-3">
          <div>
            <Label hint={def.hint}>Pick any that fit</Label>
            <ChipMultiSelect
              options={CHARACTER_CHIPS}
              value={p.characterChips}
              onChange={p.setCharacterChips}
            />
          </div>
          <div>
            <Label>Add your own words (optional)</Label>
            <input
              ref={(el) => (focusable.current = el)}
              className="w-full"
              placeholder="e.g. like a band tightening, like pins and needles…"
              value={p.characterOther}
              onChange={(e) => p.setCharacterOther(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
        </div>
      );

    case "radiation":
      return (
        <div className="space-y-3">
          <RadioRow
            options={[
              { value: "no", label: "Stays in one spot" },
              { value: "yes", label: "It spreads / moves" },
            ]}
            value={p.radiationYes}
            onChange={(v) => p.setRadiationYes(v as "yes" | "no")}
          />
          {p.radiationYes === "yes" && (
            <div>
              <Label>Where does it spread to?</Label>
              <input
                ref={(el) => (focusable.current = el)}
                className="w-full"
                placeholder="e.g. into the left arm, down the back of the leg…"
                value={p.radiationWhere}
                onChange={(e) => p.setRadiationWhere(e.target.value)}
                onKeyDown={onKey}
              />
            </div>
          )}
        </div>
      );

    case "associations":
      return (
        <div className="space-y-3">
          <div>
            <Label hint={def.hint}>Common ones</Label>
            <ChipMultiSelect
              options={ASSOCIATION_CHIPS}
              value={p.associationChips}
              onChange={p.setAssociationChips}
            />
          </div>
          <div>
            <Label>Anything else?</Label>
            <input
              ref={(el) => (focusable.current = el)}
              className="w-full"
              placeholder="e.g. blurred vision, swelling, blood in urine…"
              value={p.associationOther}
              onChange={(e) => p.setAssociationOther(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
        </div>
      );

    case "time_course":
      return (
        <div className="space-y-3">
          <RadioRow
            options={[
              { value: "constant", label: "Constant" },
              { value: "intermittent", label: "Comes and goes" },
            ]}
            value={p.timePattern}
            onChange={(v) => p.setTimePattern(v as "constant" | "intermittent")}
          />
          <div>
            <Label>Any pattern? (optional)</Label>
            <input
              ref={(el) => (focusable.current = el)}
              className="w-full"
              placeholder="e.g. worse at night, every few hours, around meals…"
              value={p.timeNote}
              onChange={(e) => p.setTimeNote(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
        </div>
      );

    case "exacerbating_relieving":
      return (
        <div className="space-y-3">
          <div>
            <Label>What makes it worse?</Label>
            <input
              ref={(el) => (focusable.current = el)}
              className="w-full"
              placeholder="e.g. coughing, moving, eating fatty food…"
              value={p.worse}
              onChange={(e) => p.setWorse(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
          <div>
            <Label>What makes it better?</Label>
            <input
              className="w-full"
              placeholder="e.g. rest, paracetamol, sitting forward, ice pack…"
              value={p.better}
              onChange={(e) => p.setBetter(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
        </div>
      );

    case "severity":
      return (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <input
              ref={(el) => (focusable.current = el)}
              type="range"
              min={0}
              max={10}
              step={1}
              value={p.severity}
              onChange={(e) => p.setSeverity(Number(e.target.value))}
              className="flex-1"
            />
            <div className="text-2xl font-bold tabular-nums w-12 text-center">
              {p.severity}
              <span className="text-xs text-muted">/10</span>
            </div>
          </div>
          <SeverityScale value={p.severity} onChange={p.setSeverity} />
          <div className="text-xs text-muted">{severityHint(p.severity)}</div>
        </div>
      );

    default:
      return null;
  }
}

/* ----------------------- Reusable bits ----------------------- */

function Label({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="text-sm">
      <span className="font-semibold text-text">{children}</span>
      {hint && <span className="ml-2 text-muted opacity-80">— {hint}</span>}
    </div>
  );
}

function ChipMultiSelect({
  options,
  value,
  onChange,
}: {
  options: string[];
  value: string[];
  onChange: (next: string[]) => void;
}) {
  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {options.map((opt) => {
        const active = value.includes(opt);
        return (
          <button
            type="button"
            key={opt}
            onClick={() =>
              onChange(active ? value.filter((x) => x !== opt) : [...value, opt])
            }
            className={
              "px-2.5 py-1 rounded-full text-xs transition border " +
              (active
                ? "bg-primary text-white border-primary"
                : "bg-white/60 border-border/70 text-muted hover:bg-white/80")
            }
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

function RadioRow({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="mt-1 flex flex-wrap gap-2">
      {options.map((o) => {
        const active = value === o.value;
        return (
          <button
            type="button"
            key={o.value}
            onClick={() => onChange(o.value)}
            className={
              "px-3 py-1.5 rounded-xl text-sm border transition " +
              (active
                ? "bg-primary text-white border-primary"
                : "bg-white/60 border-border/70 text-muted hover:bg-white/80")
            }
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function SeverityScale({
  value,
  onChange,
}: {
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <div className="grid grid-cols-11 gap-1">
      {Array.from({ length: 11 }).map((_, n) => {
        const active = n === value;
        return (
          <button
            type="button"
            key={n}
            onClick={() => onChange(n)}
            className={
              "h-9 rounded-md text-xs font-semibold transition border " +
              (active
                ? "bg-primary text-white border-primary"
                : "bg-white/60 border-border/70 text-muted hover:bg-white/80")
            }
            aria-label={`Severity ${n}`}
          >
            {n}
          </button>
        );
      })}
    </div>
  );
}

function severityHint(v: number): string {
  if (v === 0) return "No pain or discomfort at all.";
  if (v <= 2) return "Mild — you barely notice it most of the time.";
  if (v <= 4) return "Uncomfortable but not interfering much with daily activity.";
  if (v <= 6) return "Distracting — hard to ignore, affects what you can do.";
  if (v <= 8) return "Severe — hard to focus on anything else.";
  return "Worst imaginable — disabling, can't function.";
}

/* ----------------------- Compose markdown ----------------------- */

function composeMarkdown(answers: IntakeAnswer[]): string {
  const lines = answers
    .filter((a) => a.answer && a.answer !== "(skipped)")
    .map((a) => `- **${a.letter_label}:** ${a.answer}`);
  return `I'd like to describe my symptoms using the SOCRATES framework:\n\n${lines.join("\n")}`;
}

function combineChips(chips: string[]): string {
  return chips.join(", ");
}

function joinNonEmpty(parts: (string | null | undefined)[], sep: string): string {
  return parts.map((p) => (p ?? "").trim()).filter(Boolean).join(sep);
}
