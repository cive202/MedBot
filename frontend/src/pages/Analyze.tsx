import { useMemo, useState } from "react";
import FileDropzone from "@/components/FileDropzone";
import XrayViewer, { type XrayResult } from "@/components/XrayViewer";
import MriViewer, { type MriResult } from "@/components/MriViewer";
import { api, apiErrorMessage } from "@/lib/api";

type Tab = "document" | "xray" | "mri";

interface DocResult {
  kind: string;
  mime: string;
  summary: string;
  key_findings: string[];
  values_of_concern: { name: string; value: string; concern: string }[];
  questions_to_ask_doctor: string[];
  plain_language_glossary: { term: string; meaning: string }[];
  extracted_chars?: number | null;
}

const MAX = 20 * 1024 * 1024;

const TAB_LABELS: Record<Tab, string> = {
  document: "Medical document",
  xray: "X-ray",
  mri: "MRI",
};

const TAB_HEADINGS: Record<Tab, string> = {
  document: "Analyze a medical document",
  xray: "Analyze an X-ray image",
  mri: "Analyze an MRI slice",
};

const TAB_BLURBS: Record<Tab, string> = {
  document:
    "Upload a PDF or an image of a lab report, prescription, or discharge summary. MedGemma will explain the document in plain language.",
  xray:
    "Upload a PNG/JPEG of an X-ray image. MedGemma vision will describe possible findings and recommend a follow-up direction.",
  mri:
    "Upload one PNG/JPEG slice from an MRI study. MedGemma vision will guess the body region, sequence (T1/T2/FLAIR/…), plane, and describe what's visible.",
};

const TAB_ACCEPT: Record<Tab, string> = {
  document: ".pdf,image/*",
  xray: "image/png,image/jpeg,image/webp",
  mri: "image/png,image/jpeg,image/webp",
};

const TAB_HINT: Record<Tab, string> = {
  document: "PDF or image, up to 20 MB",
  xray: "PNG/JPEG/WebP, up to 20 MB",
  mri: "PNG/JPEG/WebP, up to 20 MB · one slice at a time",
};

export default function Analyze() {
  const [tab, setTab] = useState<Tab>("document");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [doc, setDoc] = useState<DocResult | null>(null);
  const [xray, setXray] = useState<XrayResult | null>(null);
  const [mri, setMri] = useState<MriResult | null>(null);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);

  function resetResults() {
    setDoc(null);
    setXray(null);
    setMri(null);
    setErr(null);
  }

  async function submit() {
    if (!file) return;
    setBusy(true);
    resetResults();

    const fd = new FormData();
    fd.append("file", file);
    const headers = { "Content-Type": "multipart/form-data" };

    try {
      if (tab === "document") {
        const r = await api.post<DocResult>("/api/analyze/document", fd, { headers });
        setDoc(r.data);
      } else if (tab === "xray") {
        const r = await api.post<XrayResult>("/api/analyze/xray", fd, { headers });
        setXray(r.data);
      } else {
        const r = await api.post<MriResult>("/api/analyze/mri", fd, { headers });
        setMri(r.data);
      }
    } catch (e) {
      setErr(apiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      <div className="glass p-2 inline-flex gap-1">
        {(["document", "xray", "mri"] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => {
              setTab(t);
              setFile(null);
              resetResults();
            }}
            className={
              "px-4 py-2 rounded-xl text-sm transition " +
              (tab === t
                ? "bg-primary text-white font-semibold"
                : "hover:bg-white/80")
            }
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      <div className="glass p-6 space-y-4">
        <h1 className="text-xl font-semibold">{TAB_HEADINGS[tab]}</h1>
        <p className="text-sm text-muted">{TAB_BLURBS[tab]}</p>

        <FileDropzone
          accept={TAB_ACCEPT[tab]}
          maxBytes={MAX}
          selected={file}
          onFile={setFile}
          onClear={() => setFile(null)}
          hint={TAB_HINT[tab]}
        />

        <div className="flex items-center gap-3">
          <button
            onClick={submit}
            disabled={!file || busy}
            className="btn-primary disabled:opacity-50"
          >
            {busy ? "Analyzing…" : "Analyze"}
          </button>
          {err && <div className="text-red-700 text-sm">{err}</div>}
        </div>

        {tab === "mri" && (
          <div className="text-[11px] text-muted border-t border-border/40 pt-3 leading-relaxed">
            MRI studies are normally a stack of 30–300 slices. One slice gives MedGemma only a
            partial view, so treat results as informational. Use the slice with the most obvious
            finding for best results.
          </div>
        )}
      </div>

      {doc && <DocumentResult result={doc} />}
      {xray && previewUrl && <XrayViewer imageUrl={previewUrl} result={xray} />}
      {mri && previewUrl && <MriViewer imageUrl={previewUrl} result={mri} />}
    </div>
  );
}

function DocumentResult({ result }: { result: DocResult }) {
  return (
    <div className="glass p-6 space-y-4">
      <h2 className="text-lg font-semibold">Summary</h2>
      <p className="text-sm">{result.summary}</p>

      {result.key_findings.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wider text-muted mt-4">Key findings</h3>
          <ul className="list-disc pl-5 text-sm space-y-1">
            {result.key_findings.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {result.values_of_concern.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wider text-muted mt-4">Values of concern</h3>
          <div className="space-y-2">
            {result.values_of_concern.map((v, i) => (
              <div
                key={i}
                className="rounded-lg border border-amber-400/40 bg-amber-400/10 p-3 text-sm"
              >
                <div className="font-medium">
                  {v.name}: {v.value}
                </div>
                <div className="text-muted">{v.concern}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {result.questions_to_ask_doctor.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wider text-muted mt-4">
            Questions to ask your doctor
          </h3>
          <ul className="list-disc pl-5 text-sm space-y-1">
            {result.questions_to_ask_doctor.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {result.plain_language_glossary.length > 0 && (
        <div>
          <h3 className="text-sm uppercase tracking-wider text-muted mt-4">Glossary</h3>
          <dl className="text-sm space-y-1">
            {result.plain_language_glossary.map((g, i) => (
              <div key={i}>
                <dt className="font-medium inline">{g.term}: </dt>
                <dd className="inline text-muted">{g.meaning}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  );
}
