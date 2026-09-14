"use client";

import { useEffect, useRef, useState } from "react";
import { deleteDocument, listDocuments, uploadDocument } from "@/lib/documents";
import type { DocumentItem, DocumentStatus } from "@/lib/types";

const STATUS_STYLES: Record<DocumentStatus, string> = {
  UPLOADING: "text-white/50",
  PROCESSING: "text-amber-400",
  EMBEDDING: "text-amber-400",
  READY: "text-emerald-400",
  FAILED: "text-red-400",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPanel({ onClose }: { onClose: () => void }) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setDocuments(await listDocuments());
    } catch {
      setError("Could not load documents.");
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(() => {
      setDocuments((prev) => {
        if (prev.some((d) => d.status === "UPLOADING" || d.status === "PROCESSING" || d.status === "EMBEDDING")) {
          refresh();
        }
        return prev;
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const doc = await uploadDocument(file);
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    await deleteDocument(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  }

  return (
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-lg rounded-xl border border-white/10 bg-[#161922] p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Knowledge base</h2>
          <button onClick={onClose} className="text-white/50 hover:text-white">
            &times;
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md,.docx"
          onChange={handleFileSelected}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="w-full rounded-lg border border-dashed border-white/20 py-3 text-sm text-white/70 transition hover:border-blue-500 hover:text-white disabled:opacity-50"
        >
          {uploading ? "Uploading..." : "+ Upload a document (PDF, TXT, MD, DOCX)"}
        </button>

        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

        <div className="mt-4 max-h-80 space-y-2 overflow-y-auto">
          {documents.length === 0 ? (
            <p className="py-6 text-center text-sm text-white/40">No documents yet.</p>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-lg border border-white/10 px-3 py-2 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-white/90">{doc.filename}</p>
                  <p className="text-xs text-white/40">
                    {formatSize(doc.size_bytes)} ·{" "}
                    <span className={STATUS_STYLES[doc.status]}>{doc.status.toLowerCase()}</span>
                    {doc.error_message ? `: ${doc.error_message}` : ""}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="ml-2 text-white/40 hover:text-red-400"
                  aria-label="Delete document"
                >
                  &times;
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
