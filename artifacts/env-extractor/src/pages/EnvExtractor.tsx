import { useState, useRef, useCallback } from "react";

const styles = {
  root: {
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    background: "#0a0a0a",
    minHeight: "100vh",
    color: "#e2e8f0",
    padding: "20px",
    boxSizing: "border-box" as const,
  },
  header: {
    display: "flex",
    alignItems: "baseline",
    gap: "12px",
    borderBottom: "1px solid #1e293b",
    paddingBottom: "14px",
    marginBottom: "22px",
  },
  title: {
    fontFamily: "'Space Mono', 'Courier New', monospace",
    color: "#7dd3fc",
    fontSize: "15px",
    fontWeight: "bold",
    letterSpacing: "0.05em",
  },
  version: {
    color: "#334155",
    fontSize: "11px",
  },
  dropzone: (active: boolean, hasFiles: boolean) => ({
    border: `2px dashed ${active ? "#7dd3fc" : hasFiles ? "#22d3ee44" : "#1e293b"}`,
    borderRadius: "8px",
    padding: "28px 20px",
    textAlign: "center" as const,
    cursor: "pointer",
    background: active ? "#0f172a" : "transparent",
    transition: "all 0.15s",
    marginBottom: "14px",
  }),
  dropLabel: {
    color: "#64748b",
    fontSize: "12px",
    marginBottom: "6px",
  },
  fileList: {
    marginTop: "10px",
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "6px",
    justifyContent: "center",
  },
  fileTag: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: "4px",
    padding: "3px 8px",
    fontSize: "11px",
    color: "#7dd3fc",
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  removeBtn: {
    background: "none",
    border: "none",
    color: "#475569",
    cursor: "pointer",
    padding: "0",
    fontSize: "13px",
    lineHeight: 1,
  },
  btnRow: {
    display: "flex",
    gap: "8px",
    marginBottom: "20px",
    flexWrap: "wrap" as const,
  },
  buildingRow: {
    display: "flex",
    gap: "8px",
    marginBottom: "14px",
    flexWrap: "wrap" as const,
  },
  buildingBtn: (active: boolean) => ({
    background: active ? "#7dd3fc" : "transparent",
    color: active ? "#0a0a0a" : "#7dd3fc",
    border: `1px solid ${active ? "#7dd3fc" : "#1e293b"}`,
    borderRadius: "6px",
    padding: "9px 18px",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: "12px",
    fontWeight: "bold",
    cursor: "pointer",
    letterSpacing: "0.05em",
  }),
  btnPrimary: (disabled: boolean) => ({
    background: disabled ? "#1e293b" : "#7dd3fc",
    color: disabled ? "#475569" : "#0a0a0a",
    border: "none",
    borderRadius: "6px",
    padding: "9px 18px",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: "12px",
    fontWeight: "bold",
    cursor: disabled ? "not-allowed" : "pointer",
    letterSpacing: "0.05em",
  }),
  btnSecondary: {
    background: "transparent",
    color: "#475569",
    border: "1px solid #1e293b",
    borderRadius: "6px",
    padding: "9px 18px",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: "12px",
    cursor: "pointer",
    letterSpacing: "0.05em",
  },
  btnCopy: (copied: boolean) => ({
    background: "transparent",
    color: copied ? "#4ade80" : "#7dd3fc",
    border: `1px solid ${copied ? "#4ade80" : "#7dd3fc"}`,
    borderRadius: "6px",
    padding: "9px 18px",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: "12px",
    cursor: "pointer",
    letterSpacing: "0.05em",
  }),
  roomInput: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: "6px",
    padding: "9px 12px",
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: "12px",
    color: "#e2e8f0",
    width: "180px",
    outline: "none",
  },
  roomLabel: {
    color: "#64748b",
    fontSize: "11px",
    marginBottom: "6px",
    display: "block",
  },
  error: {
    color: "#f87171",
    fontSize: "12px",
    marginBottom: "14px",
    padding: "10px 12px",
    background: "#1c0a0a",
    borderRadius: "6px",
    border: "1px solid #7f1d1d33",
  },
  output: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "18px",
    whiteSpace: "pre-wrap" as const,
    fontSize: "13px",
    lineHeight: "2",
    color: "#e2e8f0",
    letterSpacing: "0.01em",
  },
  outputLine: (line: string) => {
    if (
      line.startsWith("AB Building") ||
      line.startsWith("EF Building") ||
      line.startsWith("GH Building")
    ) {
      return { color: "#7dd3fc", fontWeight: "bold", marginTop: "4px" };
    }
    if (line.includes("⚠️")) return { color: "#fbbf24" };
    if (line.startsWith("- ")) return { color: "#e2e8f0" };
    if (line.startsWith("Room |")) return { color: "#94a3b8" };
    return { color: "#e2e8f0" };
  },
  spinner: {
    display: "inline-block",
    width: "10px",
    height: "10px",
    border: "2px solid #0a0a0a",
    borderTop: "2px solid transparent",
    borderRadius: "50%",
    animation: "spin 0.7s linear infinite",
    marginRight: "6px",
    verticalAlign: "middle",
  },
};

interface ImageFile {
  name: string;
  base64: string;
  mediaType: string;
}

const BASE_URL = import.meta.env.BASE_URL.replace(/\/$/, "");

export default function EnvExtractor() {
  const [images, setImages] = useState<ImageFile[]>([]);
  const [building, setBuilding] = useState<"AB" | "EF" | "GH" | "">("");
  const [roomOverride, setRoomOverride] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [output, setOutput] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const toBase64 = (file: File): Promise<string> =>
    new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res((r.result as string).split(",")[1]);
      r.onerror = rej;
      r.readAsDataURL(file);
    });

  const processFiles = useCallback(async (files: File[]) => {
    const processed: ImageFile[] = [];
    for (const file of files) {
      if (!file.type.startsWith("image/")) continue;
      const base64 = await toBase64(file);
      processed.push({ name: file.name, base64, mediaType: file.type || "image/jpeg" });
    }
    setImages((prev) => [...prev, ...processed]);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      processFiles([...e.dataTransfer.files]);
    },
    [processFiles],
  );

  const removeImage = (idx: number) => {
    setImages((prev) => prev.filter((_, i) => i !== idx));
  };

  const extract = async () => {
    if (!images.length) return;
    setLoading(true);
    setError("");
    setOutput("");

    try {
      if (!building) {
        setError("Select AB, EF, or GH first.");
        setLoading(false);
        return;
      }

      const response = await fetch(`${BASE_URL}/api/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          images: images.map((img) => ({ base64: img.base64, mediaType: img.mediaType })),
          roomOverride: roomOverride.trim() || undefined,
          building,
        }),
      });

      const data = (await response.json()) as { result?: string; error?: string };
      if (!response.ok) throw new Error(data.error ?? "Extraction failed");
      setOutput(data.result ?? "");
    } catch (err) {
      setError("Extraction failed: " + (err instanceof Error ? err.message : String(err)));
    }
    setLoading(false);
  };

  const copyOutput = () => {
    navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div style={styles.root}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap');
        @keyframes spin { to { transform: rotate(360deg); } }
        * { box-sizing: border-box; }
        input:focus { border-color: #7dd3fc !important; }
      `}</style>

      <div style={styles.header}>
        <span style={styles.title}>ENV EXTRACTOR</span>
        <span style={styles.version}>v0413</span>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        style={styles.dropzone(dragging, images.length > 0)}
      >
        <div style={styles.dropLabel}>
          {images.length === 0
            ? "Drop images here or tap to upload"
            : `${images.length} image${images.length > 1 ? "s" : ""} loaded`}
        </div>
        <div style={{ color: "#334155", fontSize: "11px" }}>
          TrolMaster · Zone Overview · Handwritten Sheet
        </div>
        {images.length > 0 && (
          <div style={styles.fileList}>
            {images.map((img, i) => (
              <span key={i} style={styles.fileTag}>
                {img.name.length > 20 ? img.name.slice(0, 18) + "…" : img.name}
                <button
                  style={styles.removeBtn}
                  onClick={(e) => {
                    e.stopPropagation();
                    removeImage(i);
                  }}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          style={{ display: "none" }}
          onChange={(e) => processFiles([...(e.target.files ?? [])])}
        />
      </div>

      <div style={{ marginBottom: "14px" }}>
        <span style={styles.roomLabel}>
          ROOM ID OVERRIDE — for TrolMaster / single-room images only (e.g. EF3, AB1)
        </span>
        <input
          style={styles.roomInput}
          placeholder="Leave blank for auto-detect"
          value={roomOverride}
          onChange={(e) => setRoomOverride(e.target.value)}
        />
      </div>

      <div style={styles.buildingRow}>
        {(["AB", "EF", "GH"] as const).map((code) => (
          <button
            key={code}
            style={styles.buildingBtn(building === code)}
            onClick={() => setBuilding(code)}
          >
            {code}
          </button>
        ))}
      </div>

      <div style={styles.btnRow}>
        <button
          onClick={extract}
          disabled={loading || !images.length || !building}
          style={styles.btnPrimary(loading || !images.length || !building)}
        >
          {loading ? (
            <>
              <span style={styles.spinner} />
              EXTRACTING…
            </>
          ) : (
            "EXTRACT"
          )}
        </button>
        <button
          style={styles.btnSecondary}
          onClick={() => {
            setImages([]);
            setBuilding("");
            setOutput("");
            setError("");
            setRoomOverride("");
          }}
        >
          CLEAR
        </button>
        {output && (
          <button style={styles.btnCopy(copied)} onClick={copyOutput}>
            {copied ? "COPIED ✓" : "COPY"}
          </button>
        )}
      </div>

      {error && <div style={styles.error}>{error}</div>}

      {output && (
        <div style={styles.output}>
          {output.split("\n").map((line, i) => (
            <div key={i} style={styles.outputLine(line)}>
              {line || "\u00A0"}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
