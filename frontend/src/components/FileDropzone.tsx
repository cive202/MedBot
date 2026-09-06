import { useCallback, useRef, useState } from "react";
import { Upload, X } from "lucide-react";

interface Props {
  accept: string;
  maxBytes: number;
  onFile: (f: File) => void;
  onClear?: () => void;
  selected?: File | null;
  hint?: string;
}

export default function FileDropzone({ accept, maxBytes, onFile, onClear, selected, hint }: Props) {
  const [hover, setHover] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  const accepted = useCallback(
    (f: File) => {
      setErr(null);
      if (f.size > maxBytes) {
        setErr(`File too large (${(f.size / 1024 / 1024).toFixed(1)} MB > ${(maxBytes / 1024 / 1024).toFixed(0)} MB limit).`);
        return;
      }
      onFile(f);
    },
    [maxBytes, onFile],
  );

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setHover(false);
    const f = e.dataTransfer.files?.[0];
    if (f) accepted(f);
  }

  return (
    <div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          setHover(true);
        }}
        onDragLeave={() => setHover(false)}
        onDrop={onDrop}
        className={
          "block border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition " +
          (hover ? "border-primary bg-primary/5" : "border-border/70 bg-surface/30 hover:bg-surface/50")
        }
      >
        <input
          ref={input}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) accepted(f);
          }}
        />
        {!selected ? (
          <div className="space-y-2">
            <Upload className="w-8 h-8 mx-auto text-muted" />
            <div className="text-sm">Drop a file here, or click to choose</div>
            {hint && <div className="text-xs text-muted">{hint}</div>}
          </div>
        ) : (
          <div className="flex items-center justify-between">
            <div className="text-sm">
              <div className="font-medium">{selected.name}</div>
              <div className="text-xs text-muted">{(selected.size / 1024).toFixed(0)} KB · {selected.type || "unknown"}</div>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.preventDefault();
                onClear?.();
                if (input.current) input.current.value = "";
              }}
              className="p-1 rounded hover:bg-surface/80"
              aria-label="Clear selection"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
      </label>
      {err && <div className="text-red-700 text-sm mt-2">{err}</div>}
    </div>
  );
}
